# Ordinary maintenance releases

The owner authorized this compatibility repair on 2026-09-09 to unblock normal
updates while R9 runtime adoption and the R10 trusted producer remain on hold.

## Runtime behavior

- Default Cargo builds omit `r9-workload-receipts`. They do not create or scan
  its SQLite ledger, bind durable producers, reconcile receipts at startup,
  ACK receipts, or require the R9 Doctor organ. Existing receipt data is retained.
  Explicit durable requests fail instead of being silently treated as temporary.
- Original R8 temporary workload accounting remains available. Only known,
  unbound v0 evidence can use its original completeness rule; v1/bound evidence
  cannot be downgraded by a maintenance build.
- New plans default to `completion_mode=agent_reported`. Existing strict
  anchors/evidence retain `evidence_gated`, including malformed bindings.
  Reported completion advances ordinary progress but is not verified completion.
- `capabilities.build` reports `runtime_profile_marker` and
  `r9_workload_receipts_enabled`. Explicit R9 builds use
  `--features r9-workload-receipts`; this feature does not authorize deployment.

## Publish, then activate

Use the existing verified private deployment root and its fixed source checkout.
Advance that clean checkout and the governed remote/master reference together
under the provisioning mutex, using the pinned SSH authority. Verify provisioning
custody again. The candidate must be merged and independently read back from
master; commits include `[skip ci]`, and no CI is dispatched.

Git may create freshly fetched, owned loose objects or pack/index/reverse-index files with mode
`0400` even under `umask 077`. Before custody verification, normalize only these
physical, singly linked Git object files to the required `0600` under
the same mutex. Preserve their content and reject unexpected ownership, links,
or paths; do not relax provisioning's exact private-mode checks.

Invoke the publisher from a clean environment with:

```text
AGENT_BRIDGE_DEPLOY_ROOT=<existing private root>
AGENT_BRIDGE_DEPLOY_REMOTE=<governed remote name>
AGENT_BRIDGE_DEPLOY_PROFILE=maintenance
AGENT_BRIDGE_MAINTENANCE_BASELINE=<actual active binary path>
AGENT_BRIDGE_MAINTENANCE_BASELINE_SHA256=<observed active binary SHA-256>
```

Run `scripts/deploy_from_master.sh --yes`, then the same profile/environment
with `--admit-fresh-mcp`. The baseline stays the still-active old binary until
activation. Production always builds from governed master with its private
toolchain; caller-provided binaries remain forbidden. Compilation uses two jobs
to bound memory on the shared node.

Maintenance binaries/assets go to `$ROOT/maintenance`, with independent pending,
lease and fresh-MCP records under `$ROOT/publisher-state/maintenance`. Both release
profiles use the original provisioning mutex inode. The R9 binary, pending
admission and runtime state are not maintenance publication targets.

Publication alone does not adopt services or refresh existing MCP processes.
Before activation, test the candidate through the existing wrapper using its
explicit binary/asset overrides, retaining the real configuration and state
selection. Confirm an online SQLite backup made with SQLite's backup API and
the compatibility of any rollback binary. Do not raw-copy an active WAL family.

On the existing Linux or macOS legacy entry, run
`scripts/activate-maintenance-release.py plan` with `--deploy-root`,
`--legacy-wrapper`, `--expected-binary-sha256`, `--expected-wrapper-sha256`, and
the exact `--admission-receipt`. The helper verifies private payload custody and
the independent fresh-MCP admission. It freezes the declared payload into
`maintenance/releases/<binary-sha>-<asset-sha>/`; aliases point to that fixed
release, so a later publication cannot change the active inputs.

Quiesce only the services being switched, then run the same arguments with
`activate`. The wrapper/configuration/state paths are preserved. The helper
switches the binary, declared audio files/policies and runtime scripts while
retaining local audio models. Existing validated maintenance aliases can be
updated in the same way. Each alias has a same-parent backup; the private
activation manifest records exact before/after identities. Entries switch in
sequence, with a short rename/create gap; the service pause covers this window.
Caught failures restore completed moves in reverse order; an interrupted
operation has an explicit recovery manifest. Legacy FUSE power-loss atomicity
is not established by these checks.

Restart the intended services and verify their actual executable identity,
health endpoints, and a fresh MCP through the actual wrapper. Keep rollback
backups and the private activation manifest. `rollback --manifest <path>` uses
the original bound arguments and refuses changed aliases/backups. It restores
files, not SQLite: do not erase concurrent production writes to undo a binary
deployment. Existing MCP clients retain the old executable until they reconnect.

On macOS the helper requires a signed Mach-O, verifies its signature, and
freezes releases using native `renameatx_np(RENAME_EXCL)`. Linux retains ELF
validation and `renameat2(RENAME_NOREPLACE)`. Both refuse an existing target.
The same backup/manifest recovery rules apply on both platforms. The Mac
fixture suite compiles and signs disposable native binaries, exercises actual
activation and rollback, and rejects unsigned or foreign-format candidates.

This helper adaptation does not provision a production Mac root or qualify the
entire publisher/launchd sequence. A valid private publisher root and independent
fresh-MCP receipt remain required; never synthesize these from fixture receipts.
Production launchd quiescence, SQLite backup, and actual service identity/health
checks remain the caller's responsibility as described above.

The legacy HOME entry may live on a filesystem with permissive synthetic modes.
It remains an owner-local compatibility entry; this procedure does not describe
it as a private trusted root or adopt the R9 service/state architecture.

## Focused checks

Run plan Store/MCP compatibility tests in both feature modes; run temporary R8
and durable R9 tests in their appropriate modes. The maintenance profile,
publisher lease, post-build race, pinned asset, audio parity and maintenance
activation regression suites cover the release path. Test passes establish
compatibility mechanics, not R9/R10 value or a successful live adoption.
