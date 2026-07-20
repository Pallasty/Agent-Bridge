# BioCortex Track B S21B-A3: post-integration refreeze and double rebuild

Date: 2026-07-19

## Purpose

S21B-A3 is the build-evidence successor to the S21B-A2 unsigned-subject
contract review.  Its immutable predecessor is integration
`65614271a7170d52c1eaef78ff3ec35cc02fdae5`, tree
`dd889e6e7700aef3d384cc7add39b5341f52b83a`.  A2 added nine contract-review
paths without changing Cargo.lock or the four role sources.

This stage refreezes the final A3 integration and performs two offline builds
from two independently extracted Git archives.  It does not generate the
replacement unsigned subject.  A successful external receipt may unlock only
an external subject-generation and independent-verification stage.

## Required build boundary

- exact ordinary two-parent integration, with the A3 source commit as second
  parent and A2 integration as first parent;
- exact source/integration tree equality and identical frozen A3 packet delta;
- two different archive roots, target directories, temporary directories and
  writable Cargo layers;
- a private read-only Rust 1.96.0 toolchain snapshot;
- a private Cargo snapshot containing exactly the registry tuples selected by
  the target Cargo.lock, with archive checksum and sparse-index verification;
- `cargo build --frozen --locked --offline --release -j 1` for the controller,
  observer, runner and validator targets using the frozen A1 recipes;
- byte equality of all four role outputs and equality of their independently
  recomputed raw, identity and recipe digests; and
- independent recomputation of archive, Cargo.lock, toolchain, feature, schema
  and recipe closures in both roots.

The gate must run without network access and within a 3.5 GiB memory ceiling.
No candidate-supplied expected binary or closure digest is authoritative.

## Output boundary

A source-head run may create only an ephemeral provisional receipt.  A real
receipt requires the final integration head and may be created exactly once at
an absent path outside the repository.  The receipt is canonical JSON with a
domain-separated self-hash and mode 0600.

## Nonclaims

S21B-A3 does not create a real unsigned subject, signing request, signing
message, owner anchor, key, signature, authorization envelope, external-input
admission, execution permit or live output.  It requires no owner interaction
and unlocks no side effects.
