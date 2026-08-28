# R7 shadow evidence continuity audit

Date: 2026-08-27 (America/Los_Angeles)

Status: discontinuity confirmed, historical natural sample removed from the
durable threshold, and source hardening candidate verified. M2 remains
unadmitted.

## Trigger

A read-only review of the current Resident M2 shadow ledger returned one
mechanics report and zero natural reports, while the roadmap described a prior
three-report review containing one natural sample. The audit had to determine
whether production evidence was deleted, migrated, or counted across different
state roots.

## Current evidence

The macOS production root is selected by machine-local
`AGENT_BRIDGE_STATE_DIR` and contains exactly one report:

- `shadow-8f03704a03546fa9f76f7f969aa7a3ba`;
- mode 0600, one link, 1,692 bytes;
- SHA-256
  `9ffc1c95ffba582762200e8835d7e50e6a484acfd0022199cfb2479fb2090a4e`;
- recovery trigger, verified evidence, active foreground;
- `would_wake=false` only because `foreground_session_active`;
- zero projected/actual provider calls and zero actual wakes.

The report directory and all surviving Resident entries retain 2026-08-25
09:58 filesystem timestamps. They did not receive or later delete the 18:44
natural report. A read-only installed-binary review classified the sole report
as mechanics and returned `collecting`, four threshold blockers, valid owner
basis and safe boundary, and `m2_admitted=false`. A complete before/after
snapshot proved that review changed no bytes, modes, ownership, size, mtime, or
ctime.

## Discontinuity finding

The historical report named:

- natural `shadow-0e020472e6f378f3cb451e72dcdba2ea`; and
- mechanics `shadow-b424faeb28dee44da69089ac45b91034`.

Neither original file is retained in the macOS production root, its backups,
Trash, Spotlight index, project trees, or aio2 home. The historical report
records their IDs, one report digest, and the aggregate result, but it does not
bind the review to a durable state-root identity. The bytes cannot be
revalidated or safely reconstructed from prose. The three-report invocation
therefore remains historical evidence that the task occurred, but contributes
zero durable natural reports to the current owner-review threshold.

This is a state-root continuity failure, not evidence that the current macOS
production directory deleted files. It also confirms that M2 collection is
manual and default-off: no Resident/Shadow LaunchAgent, scheduler, service, or
automatic candidate source exists.

## Hardening candidate

The source candidate adds a stable random `ledger_id` per state root plus a
separate private anchor for every report. Each anchor binds that ledger ID and
the deterministic report ID to the SHA-256 of exact report bytes. Review
exposes the ledger ID and requires a one-to-one report/anchor set; it fails
closed for a missing identity, identity mismatch, missing report, missing
anchor, extra anchor, or digest mismatch. Exact idempotent
replay may backfill an old report's anchor only after revalidating the report
and useful-owner basis; it never rewrites the report.

Verification:

- focused `resident_m2_shadow`: 14 passed, 0 failed;
- complete `resident_` suite: 41 passed, 0 failed;
- `git diff --check`: passed;
- only `crates/bridge/src/resident_m2_shadow.rs` and this bounded documentation
  set changed;
- full-repository `cargo fmt --check` remains blocked by unrelated formatting
  drift already present on `master`; the changed Rust file was formatted
  directly.

## Next gate

After review, publish and deploy the source candidate through the normal exact
build/fresh-process gates. Then replay the surviving mechanics candidate with
its exact original inputs to create the first production anchor and prove its
report bytes are unchanged. Only later genuine real-task reports retained in
that same anchored ledger may count toward the frozen threshold. No missing
historical report is reconstructed, and no scheduler, provider call, wake,
action authority, or M2 admission is added.
