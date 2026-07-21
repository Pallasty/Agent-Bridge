# Engram G1 custody cross-implementation reconciliation preregistration result

Date: 2026-07-18

Verdict:
`CROSS_IMPLEMENTATION_CUSTODY_RECONCILIATION_PREREGISTERED_DESIGN_ONLY_NO_AUTHORITY`

## Result

A source-pinned, design-only reconciliation contract now separates the custody
claims made by the Rust retained-descriptor shadow from the broader Python
authenticated-freeze adapter isolated lab. Twenty-eight comparison rows and 18
future differential probes are frozen. No row claims exact equivalence, and no
rule permits selecting the strongest property from each implementation to
manufacture a stronger combined result.

No differential harness or runtime code was added. Neither predecessor was
modified. The gate reads only checked-in public artifacts and cannot represent
real custody, authority, freeze, G1.4, or runtime enablement.

## Exact source lineage

- Rust custody source commit:
  `db27075ff3eb473b5ca779b57bd86094290dc1c6`;
- Python isolated-lab source commit:
  `bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54`;
- GitLab/GitHub master integrated before preregistration:
  `33c2c4df78ef302fd0538986b95fa40a3711ba86`;
- local conflict-resolved merge:
  `9e441542f5bf424b4b07ac105ccc1d25c1676d81`.

The only merge conflict was an additive Cargo feature-list collision between
the prior Engram custody feature and current-master BioCortex S20B. Both lines
were preserved without changing either feature.

## Frozen preregistration artifacts

- contract SHA-256:
  `d0ea62745ff239c988e5725240e0a0e44796cbce5c1b5e5a4dc499c7afa84fbc`;
- validator SHA-256:
  `1ec29777abe0d6ed5624f654aad5c685196f1a30b451241470714319c5c78c38`;
- checker SHA-256:
  `a8bef61838c664c48ec7db84c4025cb222084a2003d31da4eec9cb1ac66d9cbb`.

The executable checker pins the contract, validator, and eight complete
predecessor artifacts. Its own digest is an external Git/review identity rather
than a circular self-pin.

## Reconciliation findings

The Rust source is stricter at the local filesystem boundary: raw path grammar,
component bounds, complete absolute-ancestor retention, directory name-chain
revalidation, `O_NONBLOCK`, Darwin `O_UNIQUE`, wider Darwin stat snapshots,
private-directory metadata stability, exact APFS allowlisting, and a broader
mount fingerprint.

The Python source covers a broader synthetic composition: a fixed multi-file
input set, repository and Git-common-directory identity, public artifact
bindings, an external SQLite trust ledger double, trusted-time checks, replay
CAS, and a one-use process/key-bound synthetic capability.

Neither breadth can authenticate the other implementation. In particular:

- a Python transaction cannot upgrade the standalone Rust custody result;
- Rust path and mount strictness cannot upgrade Python ledger composition;
- stock SQLite still opens the Python ledger by pathname after a sentinel
  descriptor is retained;
- Python custody revalidation occurs inside `BEGIN IMMEDIATE` before event
  append and `COMMIT`, but no custody revalidation runs after commit; and
- neither source proves absence of Darwin ACLs, APFS clones, snapshots, or
  backup aliases.

The contract therefore records no shared atomic filesystem-and-ledger
linearization point and no descriptor-native SQLite open.

## Required future evidence

The 18 preregistered probes cover raw path spelling, absolute-ancestor and
private-parent swaps, directory metadata drift, persistent and raced hard
links, FIFO/device substitution with bounded timeout, file rebinding and byte
mutation, unknown local filesystems, mount and extended-metadata drift, public
artifact rebinding, SQLite pathname reopen swapping, mutation between
precommit and commit, postcommit mutation, and explicit ACL/copy-alias gaps.

Every probe has `authority_if_pass=false`. Two accepts remain
`OBSERVED_BOTH_ACCEPT_NO_EQUIVALENCE`; two rejects retain separate failure
causes; ACL and copy-alias cases remain `UNRESOLVED_SHARED_GAP` unless a
separately reviewed control exists.

## Verification

The dedicated checker passes. It:

- validates deterministic receipts twice;
- recursively mutates all 378 scalar contract leaves below the raw-byte pin;
- rejects list truncation, an inserted equivalence row, extra schema fields,
  CRLF byte drift, duplicate JSON fields, and symlinked contracts;
- verifies source hashes and exact Git ancestry;
- checks static source witnesses for the registered matrix claims;
- confirms there is no crate or runtime surface for the new gate;
- runs Black, Pyflakes, `py_compile`, JSON parsing, Bash syntax, and whitespace
  checks;
- reruns 13 Rust custody attacks plus the ten authenticated-envelope tests and
  their complete predecessor chain; and
- reruns the Python isolated lab's 259 adversarial assertions with
  `production_admissible=false` and `g1_4_open=false`.

An independent read-only Codex security review
(`ses-f304fe74-dbde-4064-af03-ae6bf8814060`) checked all matrix claims, probe
coverage, authority boundaries, semantic mutation architecture, source pins,
macOS Bash portability, linearization wording, and cross-file consistency. It
recomputed all three artifact hashes, reported no P0/P1/P2 findings, and
returned `VERDICT: CLEAN`.

## Non-claims and operations boundary

No real private input, key, trust root, signer identity, trusted clock, live
ledger, capability, candidate, corpus freeze, BioCortex execution, retrieval
mutation, live write, deployment, MCP registration, runtime promotion, or G1.4
state was used or opened. No remote push, master merge, forum post, or deployed
binary change occurred. The existing user-owned untracked files in the main
checkout were not touched.

## Next boundary

Only a separate disposable synthetic differential harness may follow, after
this independently reviewed matrix. It must keep the two source profiles
separately named, emit observational outcomes only, preserve all authority
fields false, and retain unresolved shared gaps. It may not load real private
inputs, widen the filesystem allowlist, select a SQLite/VFS production
strategy, add a runtime entrypoint, or open G1.4.
