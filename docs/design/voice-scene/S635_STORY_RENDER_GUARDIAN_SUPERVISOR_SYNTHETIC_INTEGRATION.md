# S635 Story render Guardian/Supervisor synthetic integration

## Status

Accepted as a default-off, source-only synthetic integration. S635 implements
the S634 GuardianV2 contract, keeps `DirectV1` as the default rollback path,
and proves the new path with repository-owned subprocess fixtures. It does not
add a product entrypoint, runtime configuration, MCP tool, real Story Worker,
model access, audio output, authority read, key access, package, or deployment.

The implementation result is `synthetic integration verified`. It is not a
runtime-adoption decision.

## Implemented boundary

`StoryRenderSupervisorConfig` now carries an internal custody mode:

- `DirectV1` remains the constructor default and preserves the S623-S631
  behavior.
- `GuardianV2` requires an explicitly injected `GuardianLaunchSpec` and has no
  product caller.

The internal start boundary is asynchronous. A GuardianV2 start returns a
`StoryRenderRun` only after the Host has validated the exact Guardian PID,
Worker PID/PGID, and execution-plan digest and sent the matching start frame.
Consequently `worker_pid()` is a truthful payload PID rather than the Guardian
PID or a provisional value.

The three new modules are crate-private and Linux-only:

- `story_render_guardian_protocol.rs` owns ABG2 and the canonical sealed plan;
- `story_render_guardian.rs` owns the generic inherited-descriptor Guardian and
  bootstrap entrypoints;
- `story_render_guardian_supervision.rs` owns Tokio-side start, bounded I/O,
  terminal validation, cancellation, deadline, exact Guardian wait, and Host
  fallback.

## ABG2 and execution plan

ABG2 uses a four-byte big-endian length prefix, `ABG2` magic, protocol version
2, fixed frame layouts, and a maximum 64-byte body. `bound`, `start`, `cancel`,
`terminal`, and `failure` frames reject unknown tags, nonzero reserved bytes,
trailing bytes, invalid PID ranges, and ambiguous PID/PGID bindings.

`WorkerExecPlanV1` is a canonical bounded binary encoding carried in a Linux
memfd. The complete encoding is limited to 65,536 bytes and contains the
absolute executable and script paths, bounded raw Unix arguments, canonical
environment map, and fixed current directory. The Host seals write, grow,
shrink, and further seal changes; the Guardian verifies seals and canonical
decoding and echoes the SHA-256 digest before payload start.

Worker `exec` success is distinguished from bootstrap success by a dedicated
close-on-exec status pipe. A real Worker `exec` failure therefore maps to
`SpawnFailed`, not to a misleading Worker exit.

## Descriptor and stream ownership

The Host creates Unix socketpairs for stdin, stdout, and stderr. The Guardian
attaches the Worker ends directly to fds 0, 1, and 2 and never relays payload
bytes. Host-side endpoints are converted to Tokio streams and preserve the
existing limits: 65,536 bytes for stdin and stdout, and 16,384 bytes for
stderr.

Fixed internal descriptors 190 through 197 cover the shared lock, control,
sealed plan, Worker streams, start gate, and exec-status channel. They are
close-on-exec for the actual payload. The synthetic payload audit proves all
eight are `EBADF` after Worker `exec`.

## Custody and cleanup

The render lock now uses last-close semantics in both modes. No custodian calls
`LOCK_UN`; this avoids premature release through a duplicated open-file
description. GuardianV2 shares custody between Host and Guardian and closes
the final descriptor only after terminal evidence and process-group absence.

Cancellation and deadline send an exact bound `cancel` frame. Guardian loss is
not treated as cleanup proof: the Host first waits or kills and reaps the exact
Guardian child, then performs TERM/KILL fallback on the recorded Worker group.
If group absence cannot be proven, the Host intentionally retains its lock
descriptor and returns `CleanupUnproven`.

A direct Worker exit with a live descendant is not success. The Guardian, as a
child subreaper, removes the residual group and reports
`WorkerExitedWithLiveGroup`; the Supervisor maps it to `WorkerFailed` only
after cleanup proof.

## Verified behavior

The S635 focused suite passes 18 cases:

- four ABG2 and sealed-plan protocol cases;
- four generic Guardian lifecycle cases, including Host EOF and residual
  descendants;
- ten Supervisor integration cases covering default mode, truthful binding,
  success output, deadline cleanup, bounded-output failures, malformed and
  empty responses, nonzero exit, Guardian spawn failure, bound rejection,
  Worker exec failure, Guardian loss fallback, residual descendants, and the
  payload descriptor audit.

The S623-S631 regression suite passes 55 cases. This preserves DirectV1 stream,
cleanup, admission, replay, durable sequence, and crash behavior after making
the internal start API asynchronous. Targeted Clippy passes for all three S635
test targets; unrelated pre-existing Bridge warnings remain outside this
bounded change.

## Rollback

No runtime rollback action is needed because GuardianV2 is not enabled. Source
rollback selects `DirectV1` for future synthetic admissions. Both modes retain
the same lock pathname and namespace, so mode selection cannot overlap an
in-flight render owned by the other mode.

## Nonclaims

S635 does not prove compatibility with the real Python Story Worker or Qwen3
TTS, model or GPU behavior, audio quality, simultaneous Host and Guardian
loss, adversarial session/process-group escape, PID-reuse closure,
cgroup/systemd custody, uninterruptible sleep, kernel or power failure,
cross-host exclusion, runtime configuration adoption, deployed-binary
adoption, MCP visibility, client refresh, or human audibility.

## S636 gate

The next bounded gate should be
`story_render_guardian_runtime_adoption_review`. It should compare the actual
Story Worker invocation, installed runtime composition, configuration and
rollback surface, packaging, and deployment evidence against this synthetic
contract. S636 remains review-only: real Worker/model/audio execution,
configuration enablement, MCP exposure, binary deployment, and playback need
separate later authority.
