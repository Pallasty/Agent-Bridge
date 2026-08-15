# S632 Story render descendant custody review

## Status

Accepted as a source-only architecture review. S632 selects the next bounded
prototype; it does not implement a Guardian, modify the current Supervisor,
spawn a Worker, create or kill a cgroup, create a systemd unit, render audio,
enable a runtime surface, or deploy a binary.

## Finding

S631 proves two different properties that must not be conflated:

- cancellation reaches the current process-group cleanup path and reaps the
  directly supervised Worker plus a cooperative term-ignoring descendant;
- abrupt Host exit kills only the direct Worker through
  `PR_SET_PDEATHSIG` and recovers the Host-owned render lock.

The second result is not descendant-tree custody. Linux applies
`PR_SET_PDEATHSIG` to the calling process and clears the setting in a forked
child. A descendant that survives the direct Worker therefore has no inherited
parent-death signal. The S631 test already states this nonclaim, and S632 keeps
it explicit.

There is a second race hidden behind cleanup: the current Host owns the lock.
If the Host exits, the kernel may release that lock before an independent actor
has removed old descendants. A new Host could then admit another render while
the old process tree still exists. Descendant cleanup and lock continuity must
therefore have the same custodian.

## Threat boundary

The selected baseline covers one userspace-custodian failure at a time:

- Host loss while the Guardian survives;
- Guardian loss while the Host survives;
- Worker exit before descendants;
- cancellation, timeout, malformed startup, and descendants that retain the
  Worker process group but ignore `SIGTERM`.

It does not claim protection from simultaneous Host and Guardian loss,
privileged or adversarial descendants that escape the process group, migration
out of a future cgroup, uninterruptible kernel sleep, kernel panic, power loss,
or cross-host execution. Those require a kernel- or service-manager-owned
process set and a separate deployment profile.

## Mechanism assessment

| Mechanism | Useful property | Limitation | S632 decision |
|---|---|---|---|
| `PR_SET_PDEATHSIG` | Direct Worker dies with its parent | Cleared by fork; no descendant-set ownership | Retain as direct defense |
| session/process group | Portable TERM/KILL target for inherited membership | A process can escape with a new session/group | Retain as bounded signal set |
| child subreaper | Adopts orphan descendants and can wait for them | Does not itself stop or contain them | Retain in Guardian |
| pidfd | Race-resistant identity and exit observation for one process | Not a descendant-set handle | Defer as complementary hardening |
| repository Guardian | Survives Host EOF and preserves current protocol/stdio boundaries | Adds a protocol and one more userspace failure domain | Select for S633 |
| cgroup v2 | Kernel-owned recursive kill set; handles fork/migration races | Needs a writable delegated non-root subtree | Defer as stronger profile |
| transient systemd unit | External manager owns a cgroup lifecycle | Changes parent/stdio/deployment semantics and needs a healthy manager | Reject as baseline; keep as optional profile |

The machine has cgroup v2 and a `cgroup.kill` file for the current session
scope, but that scope and kill file are root-owned, no writable per-render
delegation was proven, and the user systemd manager reports `degraded`.
S632 therefore does not mutate cgroups or experimentally create a unit.

## Selected architecture

S633 may prototype a repository-owned Guardian outside the Worker process
group. The Guardian becomes a child subreaper, owns the direct Worker, and
retains the same `flock` open-file-description as the Host. The Host and
Guardian both keep descriptor copies as single-failure fallback custody.

Neither copy may call `LOCK_UN`. Linux associates `flock` with the open file
description shared by forked or duplicated descriptors, and the lock remains
until explicit unlock or the last duplicate closes. Explicit unlock from
either copy would unlock both custodians. The current `HostLock::drop()` calls
`LOCK_UN`, so runtime integration must introduce a different transferred-lock
state; reusing that destructor is forbidden.

The protocol has four phases:

1. The Host acquires the lock and creates close-on-exec control, event, and
   private start-gate channels.
2. It spawns the Guardian with only fixed, explicitly inherited descriptors.
   The Guardian validates them and enables child-subreaper behavior.
3. The Guardian forks a bootstrap. The bootstrap sets its direct parent-death
   signal and creates its Worker session/group before blocking. The Guardian
   reports Guardian PID, Worker PID, and PGID while payload execution remains
   gated. Only after the Host records and acknowledges that identity may the
   Guardian open the start gate and allow payload `exec`.
4. The payload inherits neither the lock nor custody-protocol descriptors.
   Normal completion is not terminal while any member of the recorded group
   remains. Cleanup is TERM, bounded grace, KILL, direct/adopted-child wait,
   group-absence proof, then last-close lock release.

The Host owns the sole write end of the Guardian liveness channel. Host loss
therefore appears as EOF. The reverse event channel gives the Host a Guardian
loss signal. If the Guardian fails before payload start, the closed gate and
direct parent-death behavior prevent payload execution. If it fails after the
Worker identity was reported, the still-live Host retains the lock and performs
fallback group cleanup before closing its descriptor.

This deliberately favors a blocked lock over an unproven release. If group
absence cannot be established, the surviving custodian retains its descriptor
and reports manual-recovery-required. Availability is subordinate to excluding
overlapping renders.

## Why cgroup v2 is not discarded

The Linux cgroup v2 interface states that `cgroup.kill` recursively sends
`SIGKILL` and handles concurrent forks and migrations. That is a stronger
process-set boundary than a process group. It remains the preferred hardening
profile once Agent-Bridge can prove a delegated, non-root, per-render subtree
and cleanup permissions without widening runtime privilege. At that point it
can also close the simultaneous Host-and-Guardian-loss and process-group-escape
nonclaims.

systemd transient service custody is another possible way to obtain a managed
cgroup, but it is not transparent: service mode changes the parent process and
execution environment, while scope mode changes who must remain as the
launcher. Its stdio/result transport, user-manager health, unit naming,
garbage collection, and deployment dependency need a separate decision.

## S633 gate

The next unit is
`story_render_guardian_protocol_and_synthetic_custody_prototype`. It may build
only a dormant repository Guardian protocol and synthetic lifecycle harness.
It must prove:

- payload cannot start before the Host records Worker identity;
- Host EOF cleans a term-ignoring group before lock recovery;
- Guardian loss after identity publication invokes Host fallback cleanup
  before lock recovery;
- direct Worker exit with a live descendant is not success;
- there is no explicit-unlock or last-close gap across either single failure;
- payload does not inherit lock or protocol descriptors;
- malformed or oversized protocol frames fail closed;
- the current Supervisor remains unwired and no runtime surface is enabled.

S633 cannot integrate the prototype into `story_render_supervisor.rs`. Runtime
integration, cgroup/systemd adoption, real Worker/model execution, MCP
registration, configuration, and deployment remain later gates.

## Primary references

- [PR_SET_PDEATHSIG(2)](https://man7.org/linux/man-pages/man2/pr_set_pdeathsig.2const.html)
- [PR_SET_CHILD_SUBREAPER(2)](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html)
- [process groups](https://man7.org/linux/man-pages/man2/getpgrp.2.html)
- [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)
- [pidfd_open(2)](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)
- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [systemd process killing](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html)
- [systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)
