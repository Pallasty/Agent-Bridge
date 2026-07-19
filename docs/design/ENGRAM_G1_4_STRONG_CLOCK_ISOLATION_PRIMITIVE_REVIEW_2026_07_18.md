# Engram G1.4 stronger clock-isolation primitive review

Date: 2026-07-18

Status: **static public design/security review complete; No authority**.

## Outcome

Host-native interception is rejected as the G1.4 wall-clock boundary. Adding
more nono, Seatbelt, Landlock, seccomp, time-namespace, loader-interposition,
or syscall-supervision rules cannot close the demonstrated Darwin commpage and
Linux vDSO paths, nor establish cross-platform closure over
architecture-specific hardware counters.

Two conditional design routes survive:

1. **WASI component with custom clocks** is the preferred public-synthetic
   feasibility candidate when the evaluated arm can be expressed behind a
   component ABI.
2. **QEMU TCG with icount and a fixed RTC** is the native-binary compatibility
   fallback when a component build is impossible.

Supervisor-owned authoritative time is mandatory in both routes. It prevents a
candidate-visible clock from becoming protocol authority, but it is not a
standalone clock-isolation primitive and cannot by itself satisfy the frozen
clock canary.

This review selects a research route only. It does not select a dependency,
implement a clock, authorize a synthetic run, change the frozen canary, open
candidate/private material, or open G1.4.

## Security objective

The original canary says `wall_clock_read = deny`. The accepted predecessor
proved that direct syscall denial is not equivalent to this property. The
stronger objective is therefore split into two independently owned claims:

- the candidate cannot observe the **host** wall clock or an uncontrolled
  external-time channel; and
- any time visible to the candidate is absent or defined deterministically by
  the supervisor, while authenticated protocol time remains supervisor-owned.

Network, shared host services, host filesystem timestamps, unregistered
inherited descriptors, and external entropy devices are time channels too.
Closing only the clock API while leaving one of those channels open is not an
admissible result. Equal clock policy across arms and byte-identical public
replays remain required.

The proposed split is not yet a contract change. The current
`wall_clock_read = deny` canary remains frozen and unsatisfied until a later
human-reviewed promotion gate explicitly replaces it.

## Evidence boundary

The review uses public source and the accepted public KAT only. It compiles or
applies no policy and launches no native probe, VM, WASI component, candidate,
or private evaluator.

Pinned local evidence:

- accepted KAT feature `7cd6fe023cd88ae2a816f8b10bc6ce05084f240d`;
- integrated master `92fe2facf6f27c85ec0a34a8c46e045b1aaf67e1`;
- grok-build reference `8adf9013a0929e5c7f1d4e849492d2387837a28d`;
- `nono = 0.53.0`, crates.io checksum
  `ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee`.

Pinned primary sources:

- Linux [vDSO manual](https://man7.org/linux/man-pages/man7/vdso.7.html):
  common clock functions may execute as user-space memory accesses and are not
  visible to seccomp.
- Linux [time namespaces manual](https://man7.org/linux/man-pages/man7/time_namespaces.7.html):
  monotonic and boottime are virtualized, but realtime explicitly is not.
- Linux [`PR_SET_TSC` manual](https://man7.org/linux/man-pages/man2/PR_SET_TSC.2const.html):
  timestamp-counter reads can be faulted only on x86.
- Linux [seccomp user-notification manual](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html):
  the mechanism mediates syscalls and is explicitly not itself a complete
  security policy.
- WASI [capability model](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md):
  imported interfaces, including clocks, can be link-time capabilities.
- Wasmtime WASI 46.0.1
  [`WasiCtxBuilder`](https://docs.rs/wasmtime-wasi/46.0.1/wasmtime_wasi/struct.WasiCtxBuilder.html):
  custom wall and monotonic clocks are injectable, while the defaults expose
  host clocks.
- Apple [Virtualization framework](https://developer.apple.com/documentation/virtualization):
  the public API creates macOS/Linux VMs and lists configurable devices. The
  conclusion that it lacks a published custom deterministic clock contract is
  an inference from that public API surface, not a claim about undocumented
  hypervisor internals.
- QEMU [TCG instruction counting](https://www.qemu.org/docs/master/devel/tcg-icount.html):
  icount derives virtual time from executed instructions and is incompatible
  with multi-threaded TCG.
- QEMU [record/replay](https://www.qemu.org/docs/master/system/replay.html):
  nondeterministic events, including hardware clocks, are recorded and replay
  requires icount.
- QEMU [`-rtc` invocation](https://qemu.readthedocs.io/en/v7.2.19/system/invocation.html):
  a fixed base and `clock=vm` are the documented deterministic shape for
  icount.

## Candidate matrix

| Candidate | Host clock closed? | Native binary? | Decision |
| --- | --- | --- | --- |
| nono + Seatbelt host process | No | Yes | Reject: accepted Darwin KAT retained libc/commpage paths |
| Landlock + seccomp host process | No | Yes | Reject: Landlock has no clock control and vDSO bypasses seccomp |
| Linux time namespace + seccomp + `PR_SET_TSC` | No | Yes | Reject: realtime remains and TSC control is x86-only |
| `DYLD_INSERT_LIBRARIES` / `LD_PRELOAD` interposition | No | No | Reject: static/direct/vDSO/commpage/hardware paths bypass it |
| ptrace or seccomp user notification | No | Yes | Reject: syscall mediation leaves memory/hardware paths |
| default Apple Virtualization.framework VM | Unproved | Yes | Reject until an exact custom-clock contract exists |
| WASI component + explicit custom clocks | Conditionally | No | Primary synthetic feasibility candidate |
| QEMU TCG + icount + fixed RTC | Conditionally | Yes | Native compatibility fallback candidate |
| supervisor-owned authoritative time | No | Yes | Mandatory overlay; never standalone isolation |

“Conditionally” means the public interface can express the required boundary;
this review has not run or verified it. The machine-readable contract therefore
keeps `clock_isolation_verified = false`.

## Why the host-native route is terminally rejected

### Darwin

The accepted fixed probe observed mask 15 without the filter and mask 7 with a
direct Seatbelt syscall filter. libc/commpage paths remained. The symbolic
`system-clock` operation did not compile. nono 0.53.0 also emits
`process-exec*`, `process-fork`, broad `sysctl-read`, and `system-info` allows;
its capability model contains no clock resource.

Loader interposition is compatibility glue, not a security boundary. The
accepted KAT directly established the libc/commpage bypass; it did not execute
a separate Darwin hardware-counter canary. A complete adversarial model must
also treat direct syscalls, static code, an absent interposition library, and
architecture-specific counters as unclosed until separately proved.

### Linux

The accepted fixed probe showed that seccomp could deny direct clock syscalls
while libc/vDSO paths remained. Kernel documentation confirms this is expected:
vDSO calls do not enter seccomp. Time namespaces do not cover realtime, and
`PR_SET_TSC` covers only one hardware source on x86. Combining the three narrows
the surface but still does not prove the registered cross-platform property.

ptrace and seccomp user notification inherit the same syscall-only blind spot.
They may remain useful for unrelated syscall mediation, never as proof of
complete host-clock isolation.

## Primary route: WASI component with custom clocks

The capability-runtime route moves the trust boundary from “arbitrary host
instructions” to an explicit component import graph. A future public-synthetic
preregistration must:

1. pin the Wasmtime version, component ABI, dependency tree, advisories, build
   flags, and host implementation;
2. define one fixed public component probe with no ambient host imports;
3. replace Wasmtime's default host wall and monotonic clocks with registered
   deterministic implementations;
4. omit network and host entropy imports and expose only registered read-only
   inputs plus fresh scratch;
5. bind every clock call and timer wakeup to a closed transcript;
6. prove identical outputs and clock transcripts across fresh runs; and
7. keep authenticated time exclusively in the outer supervisor.

The default Wasmtime context is not acceptable because it uses host clocks.
Omitting a required clock import may also make otherwise valid language output
fail to instantiate. A deterministic fixed or step clock is therefore the
preferred feasibility question, but using it would change the old “API call
must fail” canary into “host time is unavailable and returned time is a fixed
supervisor capability.” That semantic promotion needs human security audit.

WASI does not support arbitrary existing native binaries. If the candidate or
its dependencies cannot be expressed behind the frozen component ABI, this
route is unsupported rather than silently falling back to host execution.

## Fallback route: QEMU TCG with deterministic virtual time

The native-compatible route is full-system emulation, not an ordinary
hardware-accelerated VM. A future public-synthetic preregistration must pin:

- QEMU source and binary, machine/CPU model, firmware, kernel, initramfs, base
  image, command line, and device graph;
- TCG rather than HVF/KVM, one vCPU, and no multi-threaded TCG;
- fixed RTC base, `clock=vm`, and exact icount/record-replay settings;
- no network, virtio entropy, shared folders, audio/input devices, guest tools,
  or host-time synchronization;
- a read-only base image and one fresh bounded scratch overlay; and
- public canaries for RTC, vDSO, architecture counters, suspend/resume,
  snapshot restore, output equality, and replay equality.

QEMU's documentation calls icount a degree of deterministic execution, not
cycle-accurate emulation. Device and asynchronous-event closure must therefore
be proved rather than inferred from the launch flags. The expected cost is
substantially higher startup latency, storage, dependency/audit surface, and
lower throughput than WASI.

Apple Virtualization.framework and hardware acceleration may still be useful
for ordinary workspace isolation. They are not admitted here because the
public contract does not establish a guest clock independent of the host.

## Supervisor-owned authoritative time

The supervisor must own every protocol timestamp, boot-epoch transition,
sequence, nonce, timeout budget, and authenticated prelaunch anchor. Candidate
timestamps are payload data only and can never establish freshness, ordering,
expiry, or replay eligibility.

This follows the existing cross-boot rule: monotonic values are comparable only
within one boot epoch; a boot change requires trusted UTC and a strictly newer
checkpoint before replacing the old monotonic domain. A malformed candidate
clock must not poison the supervisor's trusted-time projection.

This overlay is mandatory even under WASI or QEMU, but it does not replace
candidate-visible deterministic time. Otherwise a candidate could still vary
its output by host time and break the frozen replay/equal-arm contract.

## Human security audit boundary

No human approval is required for static public validation, unchanged checker
reruns, fail-closed rejection, successful cleanup, or a separately
preregistered reversible public-synthetic feasibility run. If rollback or
cleanup fails, the supervisor must first persist, fsync, reopen, and verify a
minimal durable lesson before another attempt.

Human security audit is required only before trust promotion:

- promoting WASI/QEMU or another stronger primitive beyond public-synthetic
  feasibility;
- changing the frozen clock canary for candidate/private/runtime admission;
- promoting a new or upgraded Wasmtime, QEMU, nono, native-policy, VM-image, or
  custom-clock dependency into a real path;
- widening policy, opening private/candidate/capability material, first real
  G1.4 run, unblinding/rerun, or responding to suspected exposure.

This preserves Agent-Bridge's convenience rule: reversible work is automatic;
human review is a trust-boundary transition, not a per-command ceremony.

## Exact next gates

1. `G2_WASI_PREREGISTRATION`: static contract for a fixed public component and
   deterministic host clocks. It authorizes no run by itself.
2. `G2_QEMU_TCG_PREREGISTRATION`: static contract for a pinned single-vCPU TCG
   machine only if WASI compatibility is disproved or materially insufficient.
3. `G3_HUMAN_SECURITY_AUDIT`: required before either route is promoted into
   candidate/private/runtime authority.

The preferred next reversible cut is `G2_WASI_PREREGISTRATION`. It remains
design-only and must preserve an explicit QEMU fallback decision point.

## Verification

Before commit:

```bash
scripts/check-engram-g14-strong-clock-isolation-review.sh --phase precommit
```

After committing the exact seven-path change on its isolated branch:

```bash
scripts/check-engram-g14-strong-clock-isolation-review.sh --phase postcommit
```

The semantic checker locks predecessor hashes, nono metadata, source
claims/order, the nine-row candidate matrix, decision, gates, audit policy,
nonclaims, deterministic receipt, mutation rejection, exact path surface,
syntax, and absence of Python bytecode residue. It is deliberately not a
self-authenticating trust anchor: a same-commit checker cannot prove that its
own validation logic or the producer, wrapper, README, contract, and documents
were not changed together.

A passing checker run is therefore necessary but insufficient for acceptance.
An independent read-only reviewer must produce a manifest that binds its
session and PASS verdict to the exact feature commit, tree, the semantic-
checker SHA-256, and the SHA-256 of every one of the seven exact feature paths;
that manifest must then be published and verified out of band in the Agent-
Bridge forum. Until then, this review has no acceptance authority and still
grants no implementation, run, candidate, private, runtime, deployment, or
G1.4 authority.

## Nonclaims

This review does not claim that WASI or QEMU was selected, implemented, run, or
verified; that a complete native adapter exists; that the 14-canary suite ran;
that candidate/private/capability material may be opened; or that production,
deployment, runtime promotion, or G1.4 execution is authorized.
