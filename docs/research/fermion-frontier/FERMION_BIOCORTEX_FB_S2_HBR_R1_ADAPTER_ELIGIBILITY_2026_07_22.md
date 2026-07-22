# Fermion × BioCortex FB-S2 HBR-R1 adapter eligibility

Date: 2026-07-22

Machine qualification: **INDETERMINATE_SOURCE_AUTHORITY**

Operational disposition: **OPERATIONAL_NO_GO_CURRENT_CHAIN**

Authority: source-bound, one-sided public-evidence audit; no positive
qualification, adapter-construction, candidate-execution or FB-S2B authority

## Outcome first

The fixed BioCortex snapshot does not presently contain an authorized,
materialized and executable HBR-R1 adapter that can be mapped faithfully into
the Fermion residual experiment. Adapter construction and FB-S2B therefore stop
for the current chain.

This operational stop is not a machine-level `NO_GO_ADAPTER_ELIGIBILITY`
receipt. The mandatory upstream artifact-integrity gate could not complete
inside the frozen 1 GiB, zero-swap envelope: before invoking its Rust checker,
it attempted to copy a 1,042,649,166-byte toolchain `lib` tree into `/tmp`,
which is tmpfs on this host. `cp` invoked the OOM killer after the copy stage
exhausted the cgroup; the recorded victims were `python3` and two `bash`
processes. Outer redirection left a zero-byte file, but the gate emitted no JSON
receipt. It did not return an ordinary observed nonzero result, and no candidate
source was parsed, compiled, linked or executed.

The two statuses answer different questions:

| Axis | Result | Meaning |
|---|---|---|
| Frozen protocol machine status | `INDETERMINATE_SOURCE_AUTHORITY` | The required integrity gate was not observed to completion under its fixed resource contract. |
| Current-chain operating decision | `OPERATIONAL_NO_GO_CURRENT_CHAIN` | Bound static records already close the route, deny implementation/execution authority and show that the Fermion mapping evidence is absent. |

Neither status grants permission to design or run FB-S2B.

## Frozen identity and protocol

The audit binds BioCortex repository `git@github.com:pallasting/biocortex-rs.git`
at:

- commit `1539a6ff33867e4cb34f5530cfc137229f7f63f5`;
- tree `1b4eeda4bba8b0d564a216e6841de99a9dd590a2`;
- successfully fetched ref `refs/remotes/origin/main`.

Exact commit, tree, Git mode, blob, byte-count and SHA-256 identities passed for
the bound source and authority files. This establishes snapshot identity only;
it does not establish scientific validity or runtime eligibility.

FB-S2 v1 is intentionally a one-sided negative qualification performed after
manual reconnaissance, not an outcome-blind preregistration. It has
`positive_qualification_authority: false`. Even an apparently all-green v1
surface can only request a new, hash-bound positive-qualification v2; it cannot
authorize adapter construction or execution.

The final pre-receipt protocol commit is
`3236468ccffb05163860f602f321fbfd364735d0`, with tree
`49c316543a28578e5b8c5a01e0023ff021b67f47`. Its frozen identities are:

- contract SHA-256
  `f4b64721b8a04c8a0e9225224b125bc452e0acbf58375b184b0b4b1d35214049`;
- checker SHA-256
  `7d9f18be87a3cac3369d84411b126d31b72c18961dd992e71a0dafd839fc4234`.

## Bound static replay

After the resource failure, the same checker was run in source-bound static
mode without requesting the upstream gate or candidate execution. The replay
used 26,888 KiB peak RSS and 0.210 seconds inside the 1 GiB, zero-swap cgroup.
Its raw receipt has SHA-256
`1b79cdd07aef85a2f04ef02fc467d2d33e9e091e91a96146622c031b685e622c`
and 50,454 bytes; the normalized scientific result SHA-256 is
`78335d3c274db2038868074f3ef204da595b1b5b5207912b411c2f25c88ac1ad`.

Of 57 required eligibility gates, 5 passed and 52 were unmet:

| Partition | Count | Interpretation |
|---|---:|---|
| Bound source/protocol checks passed | 5 | Snapshot identity, frozen protocol and available static bindings passed. |
| Integrity/resource fields unobserved | 5 | The mandatory gate did not complete; these are not source-integrity failures. |
| Authority and implementation fields explicitly negative | 28 | Current route is closed; reopen and implementation/compile/execute authorities are false; materialized adapter anchors and execution edges are absent. |
| Fermion mapping and receipt fields missing | 19 | No hash-bound mapping, build, equivalence or independent-review evidence exists. Absence is not an observed leakage or equivalence failure. |

All identified path/hash pairs passed in the bound records: runtime 22,
custody 9, root 7, owner-hold 7 and route-closure 12. Cross-record authority
values were consistent.

The candidate manifest binds nine `.rs` source-media files by opaque hashes.
Those files are outside every Cargo and module target in the fixed snapshot.
The audit did not decode or lexically inspect their contents. The bound records
report zero `RegisteredArmExecutor` implementation heads, adapter call edges,
bound runtime subjects and accepted registry instances, and no materialized
adapter root, entry anchor, case registry or constructed/compiled/linked
candidate.

## Resource failure classification

The one permitted artifact-integrity attempt ran in systemd scope
`run-p3246649-i20016839.scope` with `MemoryMax=1,073,741,824` bytes and swap
disabled. Kernel and cgroup evidence records:

- `cp invoked oom-killer` at exactly 1,048,576 KiB usage and limit;
- zero KiB swap usage and limit;
- 1,043,861,504 file bytes and 1,043,836,928 shmem bytes at OOM;
- a hard-coded
  `cp -a --reflink=never TRUSTED_TOOLCHAIN_ROOT/lib TMP/toolchain/lib` operation;
- a toolchain library tree of 1,042,649,166 bytes across 2,539 files.

The correct classification is
`GATE_RESOURCE_ENVELOPE_INCOMPATIBILITY_UNRUNNABLE_UNDER_FROZEN_1_GIB`.
It is a host/gate resource failure, not a source-integrity failure, candidate
OOM, candidate performance failure or evidence about the HBR-R1 algorithm.
Raising the memory cap would exceed the frozen resource contract. An unchanged
retry is expected to reproduce the demonstrated resource incompatibility and
would add no scientific evidence, so it was not repeated.

## Non-claims

FB-S2 does not claim that HBR-R1 source media are absent, invalid or incapable
in principle. It does not assess BioCortex runtime behavior, a physical L=8
instance, BGL, hardware, fermionic non-Gaussianity or quantum advantage. It
does not touch Agent-Bridge memory, authorize Agent-Bridge runtime adoption or
alter mainline parameters. No performance number was produced.

The synthetic all-green and mutation unit tests are checker-logic controls
only. They are not source, runtime, mapping, equivalence or performance
evidence.

## Disposition and next admissible target

Do not build the adapter and do not start FB-S2B on this chain. A future reopen
requires all of the following as new, independently reviewable evidence:

1. a new hash-bound owner packet that explicitly reopens the route;
2. an upstream artifact-integrity gate revised to run safely within 1 GiB and
   zero swap without copying the full toolchain into tmpfs;
3. a materialized Cargo/module adapter with callable entry, implementation and
   registry evidence;
4. a hash-bound Fermion residual mapping, leakage guards, deterministic build
   and independent equivalence receipts;
5. a new positive-qualification v2 frozen against those exact artifacts.

Until then, the scientifically admissible next target is upstream evidence
qualification, not another proxy sweep and not candidate execution.
