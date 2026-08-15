# S633 Story render Guardian synthetic prototype

## Status

Verified as a source-only synthetic prototype. S633 implements the dormant
Guardian protocol and exercises real repository-owned Linux subprocesses only
under temporary test roots. It does not modify `story_render_supervisor.rs`,
register the module in `lib.rs`, invoke the real Story Worker, read authority,
load a model, render audio, change configuration, register MCP, or deploy a
binary.

## TDD evidence

The protocol test was first compiled without the source module and failed on
the missing `story_render_guardian_synthetic.rs`. After the bounded codec was
implemented, its two protocol cases passed. The lifecycle API was then added to
the test first and failed on the missing custody symbols before the subprocess
prototype was implemented.

The final focused test runs eight cases serially. Serialization makes the
process and lock timeline readable; each case still uses an independent
temporary directory and unique process group.

## Bounded protocol

The protocol is a length-prefixed binary contract, not free-form JSON:

- four-byte `ABG1` magic and version 1;
- unsigned 32-bit big-endian body length;
- maximum body size of 64 bytes;
- fixed `bound`, `start`, `cancel`, `terminal`, and `failure` frames;
- zero reserved bytes, exact frame lengths, no trailing fields;
- nonzero Linux PID bounds and `worker_pid == worker_pgid` binding.

The reader checks the announced length before allocating the body. Oversized,
truncated, wrong-magic, unknown, trailing, or PID-invalid frames fail closed.
The Guardian socket has bounded read and write timeouts.

## Startup gate and descriptor boundary

The Host acquires a 0600, single-link, no-follow `flock` file and creates a
close-on-exec Unix socket pair. Immediately before Guardian `exec`, only fixed
lock and socket descriptors are duplicated into the child. The Guardian
validates the inherited lock inode, device, mode, and link count, then restores
close-on-exec on both descriptors.

The Guardian enables `PR_SET_CHILD_SUBREAPER` and creates a close-on-exec start
pipe. The bootstrap sets `PR_SET_PDEATHSIG(SIGKILL)`, verifies its parent,
creates a new session/process group, and receives only the start-pipe read end.
It may execute the test harness bootstrap, but the synthetic payload remains
blocked until the following sequence completes:

1. Guardian sends the bound Guardian PID, Worker PID, and Worker PGID.
2. Host records and validates that identity.
3. Host sends an exact matching `start` frame.
4. Guardian writes the start byte.
5. Bootstrap closes the gate and proves the lock, Guardian socket, and gate
   descriptors are all `EBADF` before producing the payload marker.

The test observes that the payload marker is absent before step 3 and contains
`custody_fds_closed` only after the terminal event.

## Shared lock custody

Host and Guardian hold descriptors for one shared open-file-description. The
prototype never calls `LOCK_UN`; lock release is last-close only.

This produces two verified single-failure paths:

- On abrupt Host `process::exit`, the Host socket closes without Rust
  destructors. Guardian observes EOF, sends TERM to the Worker group, waits the
  fixed grace, sends KILL, waits the direct Worker, reaps adopted descendants,
  proves the group absent, and only then closes its last lock descriptor.
- When the test kills Guardian with `SIGKILL`, Host retains its descriptor and
  recorded PGID. Host performs the same TERM/KILL and group-absence proof. The
  lock remains unavailable throughout fallback and becomes available only
  after Host drops the confirmed-clean custody object.

If cleanup cannot prove group absence, Guardian parks forever while retaining
its lock descriptor. If Guardian is already lost and Host fallback cannot
prove absence, Host intentionally leaks its descriptor. These are fail-closed
manual-recovery states: availability is not exchanged for overlapping render
admission.

## Worker-exit semantics

A zero-exit direct Worker is not terminal success while its PGID still exists.
The residual-descendant fixture exits its Worker while an inherited descendant
continues to ignore TERM. Guardian detects the live group, performs bounded
cleanup, and emits `WorkerExitedWithLiveGroup` rather than `CleanSuccess`.

The term-ignoring Host-crash and Guardian-crash fixtures publish both PIDs.
Tests require every PID to be reaped or no longer live before admitting lock
recovery. All temporary roots are then removed by their owners.

## Boundaries and nonclaims

The module is included only by
`story_render_guardian_synthetic_s633.rs` through `#[path]`. It is absent from
the Bridge library and current Supervisor composition. S633 therefore proves
the selected mechanism against repository-owned fixtures, not runtime adoption
or compatibility with the real Python Story Worker.

It does not cover simultaneous Host and Guardian loss, adversarial process
group escape, cgroup/systemd custody, uninterruptible sleep, kernel or power
failure, cross-host custody, real authorization/model execution, or current
client adoption.

## S634 gate

The next gate is `story_render_guardian_supervisor_integration_review`. S634
should review the exact current Supervisor diff required to:

- replace explicit-unlock `HostLock` with a transfer-safe custody state;
- preserve bounded stdin/stdout/stderr behavior and cancellation semantics;
- define real Worker argument and result transport through the Guardian;
- retain S629 replay continuity and lock ordering;
- add rollout and rollback gates without enabling runtime or MCP.

S634 remains a review. Integrating the Guardian, running a real Worker,
changing deployment, or exposing a new tool requires a later explicit gate.
