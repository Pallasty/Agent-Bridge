# S634 Story render Guardian/Supervisor integration review

## Status

Accepted as a source-only architecture review. S634 defines the exact
default-off synthetic integration contract between the S623 Supervisor and the
S633 Guardian mechanism. It does not modify either source module, implement
ABG2, spawn a Guardian or Worker, invoke the real Story Worker, load a model,
render audio, change configuration, register MCP, build a binary, or deploy.

The implementation decision is `ready for a default-off synthetic patch`, not
`ready for runtime adoption`.

## Reviewed baseline

The review is bound to the current source tree and the S633 receipt by SHA-256.
The relevant chain is:

1. S625 acquires the host render lock before identity generation or grant
   issuance.
2. S630 reserves the S629 sequence while that lock is held and before payload
   start.
3. S623 directly spawns the Worker, owns its stdio and `Child`, and releases
   `HostLock` immediately before completing the run future.
4. S630 commits or aborts the already consumed sequence after the run future
   completes.
5. S631 proves direct-Worker cleanup and durable replay behavior, but not
   arbitrary descendant custody after abrupt Host loss.
6. S633 proves a separate Guardian mechanism against repository-owned
   subprocess fixtures, while remaining absent from the Bridge module tree.

This ordering is intentional. Busy admission does not consume identity or a
sequence. Once a sequence is reserved, every failure remains consumed. A
successful Worker result is hidden if continuity finalization fails.

## Architectural impact

The source change required by integration is high-impact despite the current
runtime impact being zero. The Guardian changes ownership of the Worker,
standard streams, exit status, cleanup, and lock lifetime. It also makes the
current synchronous start API untenable: `StoryRenderRun::worker_pid()` is
available immediately today, while a Guardian cannot publish that PID until a
bounded handshake has completed.

S635 must therefore make the internal start boundary asynchronous. There is no
current runtime caller, so this is preferable to blocking a Tokio executor
thread during Guardian startup or returning an ambiguous PID.

## Current incompatibilities

The S633 source is evidence for the custody mechanism, not a component that can
be wired into S623 unchanged:

- `HostLock::drop()` calls `LOCK_UN`. A duplicated Guardian descriptor would
  share the same open-file-description, so explicit unlock from either
  custodian would release the common lock prematurely.
- S623 owns a Tokio `Child` and its `ChildStdin`, `ChildStdout`, and
  `ChildStderr`. With a Guardian, the Guardian owns the direct Worker child.
- ABG1 reports only clean success or a small failure code. It does not carry
  the Worker's exit code or terminating signal, so the Host cannot preserve
  `status_code` and `WorkerFailed` semantics.
- `SyntheticGuardianSpec` selects behaviors of the test executable through
  environment variables. It cannot represent the real executable, script,
  argument vector, fixed environment, or current directory.
- The S633 Host control path uses blocking `std::os::unix::net::UnixStream` and
  sleeps. Calling it directly from the Supervisor would block Tokio workers.
- S633 has no Host-owned asynchronous endpoints for the Worker's bounded
  stdin/stdout/stderr contract.
- A control EOF is evidence of channel loss, not proof that the Guardian is
  dead. Host fallback must begin only after the exact Guardian child is reaped;
  otherwise two custodians could race cleanup.

## Selected integration contract

### 1. Per-admission custody mode

Add an internal `StoryRenderCustodyMode` to
`StoryRenderSupervisorConfig`:

- `DirectV1` remains the default and rollback mode for synthetic callers.
- `GuardianV2` is an explicit per-admission test configuration.

Both modes use a replacement custody-lock type that never calls `LOCK_UN`.
`DirectV1` closes its sole descriptor after existing cleanup. `GuardianV2`
duplicates one shared open-file-description into Host and Guardian custody and
releases only by last close after cleanup proof.

The lock pathname and namespace are identical across modes. This prevents a
rollback configuration from admitting a direct render while an older Guardian
render still owns custody.

### 2. Canonical Worker execution plan

The Host creates a sealed Linux memfd containing
`WorkerExecPlanV1`. Its canonical length-prefixed binary encoding contains:

- absolute Worker executable and script paths;
- bounded argument count and byte lengths using raw Unix path bytes;
- the exact fixed S620 environment map;
- `/` as the fixed current directory;
- protocol version and the fixed standard-stream descriptor layout.

The complete encoding is limited to 65,536 bytes. The Host writes it once,
seals write/grow/shrink/seal changes, computes SHA-256, and passes only the
read-only descriptor to the Guardian. The Guardian verifies the seals, exact
length, canonical ordering, digest, path bounds, environment equality, and
absence of trailing or unknown fields before spawning anything.

The `bound` frame echoes the plan digest. A mismatch cannot open the payload
start gate.

This avoids putting arbitrary `OsString` values into environment variables or
expanding the small lifecycle protocol into a bulk data channel.

### 3. Standard-stream ownership

Before Guardian spawn, the Host creates three close-on-exec Unix socketpairs:

- Host write end / Worker stdin end;
- Host read end / Worker stdout end;
- Host read end / Worker stderr end.

Only the fixed Worker ends are inherited by the Guardian. The Guardian attaches
them to Worker fds 0, 1, and 2, closes its copies immediately after Worker
spawn, and never relays payload bytes. The payload inherits neither the render
lock, Guardian control socket, execution-plan descriptor, nor start gate.

The Host wraps its endpoints in Tokio asynchronous streams and retains the
existing 65,536-byte stdin, 65,536-byte stdout, and 16,384-byte stderr limits.
Closing unused socket directions and closing the Guardian copies are required
so EOF remains truthful.

### 4. ABG2 lifecycle protocol

ABG2 retains the strict fixed-frame properties of ABG1: magic/version,
big-endian lengths, bounded bodies, exact reserved bytes, PID validation, and
rejection of unknown or trailing fields. It adds only the fields required for
real Supervisor parity:

- `bound`: Guardian PID, Worker PID/PGID, and Worker-plan SHA-256;
- `start`: exact Worker PID/PGID and plan digest;
- `cancel`: exact binding, making delayed or cross-run cancellation invalid;
- `terminal`: exact binding plus `exit_kind` (`exited` or `signaled`) and the
  corresponding code/signal;
- `failure`: bounded stage and reason codes, with binding where available.

`terminal` is legal only after the Guardian has waited the direct Worker,
reaped adopted descendants, and proven the recorded process group absent. It
does not assert that stdout is nonempty or protocol-valid; those remain Host
responsibilities after bounded EOF capture.

### 5. Asynchronous start and owned cleanup

`StoryRenderAdmission::start` and `start_story_render_supervisor` become async
at the internal boundary. Start performs the following without blocking Tokio:

1. move the already held custody descriptor into an owned supervision task;
2. create the execution plan, stream socketpairs, and Guardian control pair;
3. spawn the configured Guardian entrypoint;
4. receive and validate `bound` under the one absolute run deadline;
5. record the exact binding and send the matching `start` frame;
6. return `StoryRenderRun`, whose `worker_pid()` is now truthful.

If the caller drops the start future before the run is returned, the owned task
detects the closed readiness receiver and completes cancellation/cleanup. No
lock or Guardian child is left owned only by a cancelled stack future.

After start, one owned task concurrently writes bounded stdin, reads bounded
stdout/stderr, reads Guardian control, observes cancellation, and enforces the
remaining absolute deadline. Blocking Guardian work stays in the separate
Guardian process. Any Host fallback wait/reap operation must use an owned
blocking task or an async descriptor, never block a Tokio worker.

`StoryRenderRun::drop()` still requests cancellation. It no longer kills a
direct child: the task sends an exact ABG2 cancel and waits for clean terminal
custody. If the Guardian is reaped before clean terminal, Host fallback takes
over the recorded process group while retaining the shared lock descriptor.

## Custody state machine

The required states are:

1. `admitted`: Host owns the acquired descriptor.
2. `guardian_spawned`: Host and Guardian share custody; payload gate is closed.
3. `bound`: Host recorded exact Guardian/Worker/PGID/plan identity.
4. `running`: exact start was acknowledged and Host I/O is active.
5. `cancelling`: cancellation or deadline was sent; cleanup is still owned.
6. `terminal_clean`: exit status and group-absence proof were captured.
7. `fallback_cleaning`: exact Guardian was reaped and Host owns TERM/KILL proof.
8. `manual_recovery_required`: cleanup is unproven and custody is retained.
9. `released`: the final descriptor closed after result capture.

A normal result may leave custody only after both standard-stream result
capture and process-group absence. A Guardian channel error is never success.
If cleanup cannot be proven, the Guardian holds its descriptor or the Host
moves its descriptor into an in-process quarantine with no automatic release
API. Availability remains subordinate to exclusion of overlapping renders.

## Failure mapping

| Event | Supervisor result | Custody requirement |
|---|---|---|
| invalid/unsealed execution plan | `InvalidConfiguration` | no payload start |
| Guardian spawn failure | `GuardianSpawnFailed` | Host closes sole lock after no child exists |
| bound timeout/mismatch | `GuardianProtocolRejected` | reap Guardian, then fallback if bound exists |
| Guardian reports Worker spawn failure | `SpawnFailed` | clean Guardian terminal required |
| stdin/write or bounded-read failure | existing stream error | cancel and prove cleanup first |
| Worker nonzero exit or signal | `WorkerFailed` | terminal and stream EOF captured |
| zero exit with empty stdout | `WorkerExitWithoutResponse` | terminal captured |
| response validator rejects | `ResponseRejected` | terminal captured |
| owner cancel | `Cancelled` | returned only after cleanup proof |
| absolute deadline | `DeadlineExceeded` | returned only after cleanup proof |
| Guardian loss, fallback clean | `GuardianLost` | exact Guardian reaped first |
| group absence unproven | `CleanupUnproven` | descriptor quarantined/held |

Cleanup errors take precedence over the triggering stream, cancel, or deadline
error because releasing custody without proof would make the original error
misleadingly terminal.

## Replay continuity and lock ordering

S635 must preserve this exact externally visible order:

1. acquire render lock;
2. generate request identity;
3. reserve the durable sequence;
4. spawn Guardian;
5. record Worker binding;
6. acknowledge payload start;
7. perform bounded Worker I/O;
8. prove Worker process-group absence;
9. validate terminal status and response;
10. release Host custody;
11. commit or abort the sequence.

This intentionally preserves current S630 behavior: lock release precedes
continuity finalization, while every post-reservation failure remains replay
blocked. Finalization failure still suppresses a successful Worker response.
Independent replay roots remain independent.

## Exact S635 change surface

S635 may change only the following bounded surface:

- refactor `story_render_supervisor.rs` for custody mode, async start, last-close
  lock ownership, Guardian routing, and explicit error mapping;
- add `story_render_guardian_protocol.rs` for ABG2 and the canonical sealed
  execution plan;
- add `story_render_guardian.rs` for a generic inherited-fd entrypoint;
- adapt the S624/S625/S630 internal async call chain;
- register the two new modules as crate-private in `lib.rs`;
- add a serial S635 synthetic integration and single-failure test matrix;
- update existing S623-S631 tests for the async internal API and require direct
  mode parity.

S635 does not add a product binary, main/CLI subcommand, MCP tool, runtime
configuration reader, owner authorization path, real model Worker, audio
output, or deployment asset. Its Guardian executable is injected by the test
configuration and enters repository code only through a test subprocess
entrypoint.

## Rollout and rollback

GuardianV2 is default-off and selected per synthetic admission. DirectV1 and
GuardianV2 share the same lock namespace. Rollback changes only future
admissions back to DirectV1; it cannot switch an in-flight run or treat
Guardian loss as permission to downgrade custody.

Before any later real-Worker gate, S635 must prove:

- DirectV1 behavior/error parity for the S623-S631 suite;
- ABG2 malformed, oversized, digest, binding, and exit-status rejection;
- bounded stdio and truthful EOF with Guardian descriptor closure;
- Host EOF, Guardian loss, cancellation, deadline, Worker spawn failure,
  stream overflow, and residual-descendant paths;
- lock unavailability until group absence on every cleanup path;
- S629/S630 replay order and finalization behavior;
- no product entrypoint, runtime caller, MCP registration, model, audio, or
  deployment effect.

## Nonclaims

S634 does not prove ABG2 implementation, Supervisor/Guardian behavioral parity,
real Story Worker compatibility, simultaneous Host and Guardian loss safety,
protection from process-group escape, cgroup/systemd custody, pid-reuse closure,
runtime adoption, current-client visibility, or deployment.

## S635 gate

The next gate is
`story_render_guardian_supervisor_synthetic_integration`. It may implement the
default-off source path and synthetic fault matrix described above. Real Worker
execution, model/audio access, MCP exposure, configuration adoption, binary
packaging, and deployment remain closed behind later gates.
