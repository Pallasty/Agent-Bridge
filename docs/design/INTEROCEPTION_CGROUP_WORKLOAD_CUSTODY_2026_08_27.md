# AB interoception: delegated cgroup workload custody

Date: 2026-08-27
Status: implemented; current-node local one-shot admitted; PTY tree custody live-proven with foreground-terminal admission still pending
Scope: local Agent runtimes on Linux cgroup v2

## Decision

Agent Bridge may call a local workload's terminal CPU, peak cgroup memory
charge/usage, and peak task count complete for that workload only when all of
the following are true:

1. a fresh delegated cgroup existed before the first workload `exec`;
2. every process initially launched for that workload entered that cgroup
   through a pre-exec barrier;
3. an out-of-band supervisor remained alive outside the workload cgroup;
4. the supervisor observed the workload cgroup's final `populated 0` state;
5. it then read the required cgroup-v2 accounting files successfully; and
6. the typed, PID-free receipt reached the owning session without a protocol
   gap.

Raw child `waitid` rusage remains useful independent evidence, but it does not
satisfy this contract. `/proc` descendant sampling remains an in-flight
observation and likewise cannot be upgraded to a terminal whole-workload
claim.

The contract is fail closed. Missing systemd, a non-unified hierarchy, denied
delegation, a failed pre-exec move, an incomplete terminal read, or an
ambiguous supervisor failure leaves `complete_for_workload_tree=false`.

## Meaning of "whole workload"

The accounting boundary is the lifetime membership of one fresh
`workload/` cgroup, including all of its descendant cgroups. It is not a
process-name, PID, process-group, or sampled `/proc` boundary.

This is a cooperative same-UID boundary, not hostile containment. A process
running as the same delegated Unix user can in principle ask systemd to move a
process elsewhere or write a cgroup migration file that it is permitted to
access. This design must not claim to detect deliberate same-UID cgroup
escape. Preventing that requires a stronger authority boundary such as a
different UID, a constrained user namespace, or host policy. The receipt's
coverage therefore means:

> all execution that remained in the freshly established workload cgroup
> hierarchy from pre-exec admission until final emptiness.

An agent that intentionally migrates work out of that hierarchy invalidates
the premise. The current gate is resource custody, not a security sandbox.

## Process and cgroup topology

```text
AB parent process
  `- systemd-run --user --scope -> exec AB internal supervisor
       |                                  scope/supervisor/
       `- local agent workload           scope/workload/
            `- descendants               scope/workload/**
```

`systemd-run --scope` is used rather than a transient service because it
preserves the caller's working directory, environment, and stdio and begins
the command only after systemd has placed it in the transient scope. The
scope is requested with:

- `--user --scope --quiet --collect`;
- `--expand-environment=no` so `$` in arguments is not rewritten;
- a random, strictly validated unit name;
- `Delegate=cpu memory pids`;
- `OOMPolicy=continue`, so one workload OOM does not cause systemd to kill the
  sibling observer before it can read `memory.events`; and
- a bounded `RuntimeMaxSec` as a final leak guard. V0 defaults to 24 hours and
  accepts only an ambient `AGENT_BRIDGE_CGROUP_RUNTIME_MAX_SEC` value from 60
  seconds through seven days; per-spawn env cannot change custody policy.

The runtime ceiling is not the normal cancellation mechanism. If it fires,
systemd may kill both workload and supervisor, so a complete receipt is not
guaranteed.

## Early internal entry point

The bridge binary dispatches the internal supervisor before restoring SIGPIPE,
Tokio, clap, credential loading, logging, or any other subsystem that can
create threads. Parent loss must be reported to the supervisor as EOF/EPIPE,
not terminate it with SIGPIPE. The dispatcher is private protocol, not a
user-facing command and not part of the MCP surface.

This ordering is required because the supervisor must begin single threaded,
move itself into `supervisor/`, and empty the delegated scope root before it
enables domain controllers for children. The internal request must carry an
unforgeable or private control channel and validate its full protocol shape;
a malformed partial request fails closed and never falls through to the normal
AB CLI.

## Launch protocol

The parent first creates a private runtime-directory Unix listener. Its parent
directory is owned by the effective user with mode `0700`, and the socket is
not a public AB endpoint. The internal supervisor connects after systemd has
migrated and executed it. The parent validates `SO_PEERCRED`, a bounded fresh
nonce, and the expected protocol version before accepting READY. The socket is
unlinked after the READY/START exchange; the private runtime directory and
receipt live only as long as the in-process custody handle.

The protocol deliberately does not depend on inheriting an extra descriptor
through `systemd-run`. Although that worked in the current-node probe, it is a
weaker portability assumption and conflicts with PTY implementations that
close unrelated descriptors before exec.

Scope mode is the only admitted systemd launch form. The PID returned by the
parent spawn must equal the authenticated Unix peer PID and is then retained
through private custody/pidfd rather than rediscovered later. A transient
service, a later `MainPID` lookup, or a self-reported process identity is not
an equivalent source of custody.

The implemented v0 lifecycle is:

1. **SCOPE_STARTING** — parent starts the transient scope. No workload has
   executed.
2. **SUPERVISOR_PREPARING** — supervisor resolves its own cgroup from
   `/proc/self/cgroup`; it never trusts a parent-constructed filesystem path.
3. **READY** — supervisor has created and validated the cgroups, retained the
   migration descriptor, and successfully preflight-opened every required
   accounting endpoint. It sends READY over the private socket.
4. **START_PERMISSION** — parent explicitly authorizes the first workload
   spawn. Parent death before this message must result in zero workload execs.
5. **SPAWN/DRAINING** — the supervisor forks the target; its pre-exec hook
   performs the cgroup move. V0 has no separate STARTED frame. The leader may
   exit while descendants still populate
   the workload cgroup.
6. **TERMINAL** — workload `cgroup.events` reports `populated 0`; metrics are
   read after this observation.
7. **RECEIPT** — supervisor atomically writes one bounded, nonce/unit-bound
   receipt in the private runtime directory and mirrors the payload exit.
   The owning custody handle validates and projects that file.

There is no transparent retry after START permission or any ambiguous
activation state. The prepared launch either owns the one execution or fails
the request. This prevents a lost supervisor handshake from executing a user
request twice.

## Pre-exec membership barrier

After systemd has migrated the supervisor into the scope, the supervisor must:

1. verify `cgroup.type` is `domain`;
2. create `supervisor/` and write `0\n` to its `cgroup.procs`;
3. verify the scope root `cgroup.procs` is empty;
4. write `+cpu +memory +pids` to root `cgroup.subtree_control` and read it back;
5. create a fresh `workload/`; and
6. retain an open workload admission descriptor and preflight-open every
   endpoint required for terminal accounting.

The workload child is forked in `supervisor/`. Its pre-exec hook performs only
async-signal-safe operations and writes `0\n` to the pre-opened
`workload/cgroup.procs` descriptor. User workload code cannot run before that
write succeeds. An exec success indication therefore also proves that the
membership barrier succeeded.

The supervisor itself must never enter `workload/`; otherwise its CPU, memory,
and task count would contaminate the workload receipt and `populated` could
never reach zero while the observer remained alive.

## Required cgroup files

| Phase | File | Requirement |
| --- | --- | --- |
| preparation | `cgroup.type` | exactly `domain` |
| preparation | `cgroup.controllers` | contains each controller claimed by the receipt |
| preparation | `cgroup.subtree_control` | write and read back `cpu memory pids` |
| admission | `workload/cgroup.procs` | pre-opened; child self-migration succeeds before exec |
| lifetime | `workload/cgroup.events` | terminal read contains `populated 0` |
| cancellation | `workload/cgroup.kill` | preferred whole-subtree cancellation mechanism |
| terminal | `workload/cpu.stat` | parse bounded `usage_usec`; retain user/system fields when present |
| terminal | `workload/memory.peak` | parse one bounded peak cgroup-memory byte count |
| terminal | `workload/pids.peak` | parse one bounded task count |
| terminal | `workload/memory.events` | preserve bounded `oom` and `oom_kill` evidence |

Unknown forward-compatible keys are ignored. Missing required keys, duplicate
keys, negative values, parse overflow, a disappearing directory, or a read
before terminal emptiness makes the affected metric unavailable. A receipt
must distinguish per-metric completeness from overall completeness; for
example, a kernel without `pids.peak` must not discard otherwise trustworthy
CPU and memory values, but it also must not claim that task-peak accounting is
complete.

Because `workload/` is fresh, its counters start at the workload boundary and
need no host or supervisor baseline subtraction. CPU is cumulative for the
cgroup hierarchy; `memory.peak` is the peak hierarchical cgroup memory charge
(the peak of cgroup memory usage, including charge classes covered by the
memory controller), not process RSS or resident-set size; and `pids.peak` is a
hierarchical task-count peak.

## PID and pidfd custody

PID identity and cgroup accounting answer different questions:

- cgroup membership supplies the resource boundary;
- a pidfd supplies a non-reusable handle to a particular local process
  endpoint; and
- the Unix control socket supplies cancellation and receipt ordering.

A PID read from JSON, `/proc`, or a later map lookup never authorizes a signal.
The supervisor owns the direct workload child and its wait status. Parent-side
cancellation targets the supervisor protocol, which writes
`workload/cgroup.kill`; it does not signal the `systemd-run` wrapper PID.

The parent binds the scope child through the successful `Child::spawn` result
and authenticated `SO_PEERCRED`; custody opens and retains a pidfd for that
supervisor endpoint. Cancellation of workload members performs repeated
cgroup enumeration, opens pidfds for the observed members, revalidates their
membership, and only then signals through those handles. pidfd failure removes
that direct endpoint authority and must not be replaced with a Linux bare-PID
signal. A pidfd alone does not prove descendant coverage and cannot upgrade
wait rusage to a workload-tree claim.

PID numbers, pidfds, and cgroup paths are private custody material. They never
appear in public JSON, task events, receipts, or `Debug` output.

## Terminal receipt

The private receipt must be size bounded, versioned, nonce-bound, and PID-free.
Its public projection should include at least:

- `source = linux_cgroup_v2_systemd_delegated_scope`;
- `scope = delegated_session_workload_tree`;
- accounting status and explicit failure reason;
- controller and per-metric completeness;
- final populated state;
- CPU usage/user/system microseconds;
- peak cgroup-memory bytes, explicitly not labelled RSS/resident bytes;
- peak task count;
- OOM and OOM-kill counters;
- terminal condition; and
- `complete_for_cpu_memory_workload_tree` and separate peak-task evidence.

`complete_for_cpu_memory_workload_tree=true` requires a complete admission
chain, final `populated 0`, and successful post-empty CPU and memory reads.
Peak-task completeness remains independently visible so an older kernel that
lacks `pids.peak` cannot be mistaken for a measured task peak. Completion does
not require the process exit code to be zero: a failed or cancelled workload
can still have complete resource accounting.

For retrying runtimes, each executed generation receives a fresh workload
cgroup. CPU values are summed across complete generations; memory and task
peaks take the maximum. The session-level claim is complete only if every
executed generation has a complete receipt.

## Cancellation, parent crash, and durability

Normal cancellation first marks the runtime lifecycle cancelled so a retrying
runtime cannot admit another generation. It then sends a control message to
the current supervisor. Graceful termination performs three pidfd-bound scans
of the workload hierarchy and sends SIGTERM only to revalidated members. After
a two-second grace period it writes `workload/cgroup.kill`, waits for
`populated 0`, reads metrics, and returns a cancelled terminal receipt. The
session accounting accumulator is sealed only by its sole-reaper path, after
the last generation ends. OpenCode/Kilo retry backoff is part of this
cancellable lifecycle even when no payload PID currently exists. Killing the
supervisor directly is a last-resort loss of custody, not a successful cancel
path.

Every runtime captures a spawn-time pidfd/birth-token guard before awaiting
READY/START activation. If that launch future is cancelled, a prepared scope
receives SIGTERM (never an immediate SIGKILL) so an already-accepted START is
drained by the supervisor; an unwrapped direct child can be killed immediately.
After activation, detached wait ownership and a second return guard remain in
force until the caller actually receives the session id. Initial Store writes
run concurrently with child waiting, but `spawn` does not return until the
write attempt is acknowledged and finalisation cannot overtake it.

The control socket is also the parent-liveness channel. EOF before
START_PERMISSION exits without running a workload. EOF after START permission
causes the supervisor to kill and drain any workload that was created rather
than leave a detached scope indefinitely.

Experiments on the target node showed that stopping the parent user service
does **not** stop its separately created transient scope. Therefore socket EOF
handling and a hard `RuntimeMaxSec` are mandatory. The runtime ceiling only
prevents an eternal orphan; if it kills the supervisor, accounting remains
unavailable.

The v0 receipt uses create-new `0600` temporary output, file sync, and atomic
rename inside the private runtime directory. This prevents a live reader from
accepting a truncated receipt, but the directory belongs to the process-local
custody handle and there is no ACK or restart reconciliation. The parent must
not publish a Verified body event until it has committed the projected
receipt. A future cross-daemon guarantee needs
`RECEIPT -> durable commit -> ACK -> supervisor exit`, an atomic supervisor
spool, or a restart-reconciliation ledger. Until that exists, restart recovery
must state `receipt_commit_unknown`; it cannot reconstruct Complete from the
absence of a scope.

## Environment and stdio

Scope mode inherits the caller environment, working directory, and stdio. The
supervisor must preserve the runtime's intended stdin/stdout/stderr wiring and
apply the configured environment exactly once to the workload. Protocol bytes
travel only over the private Unix socket and never share stdout/stderr with
agent output.

`--quiet` suppresses the success banner. systemd setup errors may still appear
on stderr and are launch diagnostics, not agent output. Workload arguments are
passed behind `--` and systemd environment expansion is disabled.

Only the supervisor owns the connected control socket; payload stdio setup
must close unrelated descriptors so descendants cannot keep the
parent-liveness channel open.

## Runtime admission matrix

| Runtime class | Workload-tree claim |
| --- | --- |
| local one-shot Claude/Codex/Gemini/Auggie | implemented and current-node live admitted through the complete supervisor and pidfd protocol |
| OpenCode/Kilo retry generations | implemented and unit-proven per generation; aggregate only when every executed generation completes |
| ACP or other local child runtimes | implemented through the same supervisor and sole-reaper cancellation path; protocol lifecycle is covered by regression tests |
| interactive PTY | tree-custody interaction and TERM-to-kill escalation are live-proven; full PTY admission still requires foreground process-group, Ctrl-C, resize, and EOF conformance tests |
| Oz cloud launcher | never a local workload-root claim; local launcher/transport usage is not cloud execution usage |
| remote agent/session | local transport may be measured separately, but remote workload CPU/memory/task peak remains Unknown |

Wrapping an interactive command changes its process ancestry and can change
terminal signal delivery. The v0 supervisor restores payload signal defaults,
forwards its own TERM/HUP through an async-signal-safe pipe, and routes PTY
cancellation through custody. A deployment must still prove the real PTY
conformance cases before describing that path as admitted rather than merely
implemented.

## Fallback contract

| Failure point | Allowed behavior |
| --- | --- |
| automatic policy finds systemd/user bus/cgroup v2 unavailable before wrapping | direct-spawn fallback; waitid evidence only |
| required policy finds the platform unavailable | fail the request before spawn |
| delegation, private listener, peer credential, nonce, or READY/START fails after wrapping | kill the prepared scope and fail the request; no automatic direct re-execution |
| pre-exec migration or target exec fails | fail the one generation; no automatic direct re-execution |
| START permission was accepted but terminal receipt is lost | no re-execution; terminal accounting unavailable |
| final `populated 0` or metric read not proven | preserve known values as partial; whole-workload completeness false |
| PTY before conformance admission, Oz cloud, or remote execution | no public tree claim; PTY may be admitted only by its dedicated tests, and local evidence is never relabelled as cloud/remote evidence |

Fallback is a degradation in sensing, not in the user's requested execution.
Known raw-wait values may coexist with missing cgroup values, but the sources
and scopes remain separate.

## Current-node probe evidence

The 2026-08-27 read-only/bounded probe established:

- systemd 259.5, Linux 7.0, writable unified cgroup v2;
- `user@1000.service` delegates `cpu memory pids`;
- the current AB daemon unit itself has `Delegate=no`, but a process in a
  non-delegated user service can create a delegated transient scope;
- the delegated scope root is owned by the AB user;
- scope spawn PID/supervisor identity, sibling migration, controller
  enablement, final-empty accounting, extra-FD inheritance, and `--collect`
  cleanup all work;
- `cpu.stat`, `memory.peak`, `pids.peak`, `cgroup.kill`, and
  `memory.events` are present; and
- IO is not delegated and must remain unavailable.

The account currently has `Linger=no`. A complete logout may stop the user
manager and its scopes. This implementation must not silently change linger;
such a host lifecycle policy needs separate owner authorization.

All probe units and cgroups were removed after the audit.

## Implementation and live acceptance

The implementation landed across the shared Agent launch layer, every local
runtime, PTY lifecycle ownership, and the Bridge body-span projection. The
public projection is schema `agent_bridge.task_workload_resources.v0`; Bridge
independently rechecks its source, scope, controller set, generation counts,
terminal emptiness, required metric presence, IO status, and trust boundary
before allowing it to satisfy whole-workload CPU/memory capture.

Current-node MCP acceptance on 2026-08-27 produced these durable terminal
receipts from the debug build before deployment:

| Probe | Result |
| --- | --- |
| normal one-shot with a CPU descendant | semantic verdict `verified`; CPU `174761 us`, peak cgroup memory `2592768` bytes, peak tasks `3` |
| TERM-immune one-shot parent and descendant | cancellation escalated in about `2.5 s`; CPU `34480 us`, peak memory `4780032` bytes, peak tasks `4` |
| interactive PTY echo and follow-up | both turns observed; final receipt Complete; CPU `4269 us`, peak memory `1978368` bytes, peak tasks `1` |
| TERM-immune interactive PTY tree | semantic verdict `verified`; escalation in about `2.5 s`; CPU `68274 us`, peak memory `4837376` bytes, peak tasks `4` |

Every receipt above had one captured generation, `start_before_exec=true`,
`final_populated_zero=true`, complete CPU/memory and peak-task coverage, zero
OOM/OOM-kill events, controllers `cpu memory pids`, and
`io_accounting_status=unknown_not_delegated`. No transient
`agent-bridge-agent-*.scope` unit or probed descendant remained afterward.
The two Verified events used
`before_after_body_observation_with_delegated_cpu_memory_workload_tree`; a
complete cgroup receipt never promoted an incomplete body before/after sample
to Verified.

Final pre-deployment regression evidence was `143/143` Agent library tests,
`cargo check -p ab-agent --all-targets`, the exact Bridge delegated-receipt
gate/redaction test, and `git diff --check`. The low-risk remaining test gap is
a separately controllable abort-during-activation regression for one-shot and
ACP launches; the common activation guard is unit-tested and the analogous PTY
cancellation path is covered.

## Acceptance tests

Admission requires tests for:

1. a fast-exit child whose `/proc` entry disappears before Bridge attachment;
2. scope READY identity mismatches, pidfd failure, and forbidden service-mode
   or later-MainPID identity;
3. a leader that exits while a descendant remains alive with stdio both open
   and closed;
4. CPU, cgroup-memory charge, and concurrent-task load with nonzero expected metrics;
5. cancellation during preparation, running, leader-exited, and draining
   states;
6. parent socket loss before and after START permission;
7. malformed, truncated, replayed, oversized, and nonce-mismatched receipts;
8. controller/metric absence and numeric overflow;
9. systemd/user-bus/delegation absence with no double spawn;
10. retry-generation sum/max aggregation; and
11. cleanup of scope units and cgroup directories on success and failure.

PTY admission additionally requires real foreground-terminal tests. Deployment
acceptance must verify one installed-binary MCP run whose persisted receipt has
`final_populated_zero=true`, nonzero cgroup metrics, no PID field, and an honest
whole-workload verdict.

## Primary references

- [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [systemd cgroup delegation](https://systemd.io/CGROUP_DELEGATION/)
- [systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)
- [systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- [pidfd_open](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)
