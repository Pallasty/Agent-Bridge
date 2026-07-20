# BioCortex Track B S21B-A4: external unsigned subject generation

Date: 2026-07-19

## Decision

S21B-A4 may generate exactly one real **unsigned** subject outside the
repository only from a complete post-integration S21B-A3 refreeze receipt.
The receipt must bind the exact target commit, ordered parents, tree, archive,
Cargo.lock, four raw role binaries, four identity packets, four build recipes,
and the toolchain, feature, schema-manifest, schema-content and recipe
closures.  Null evidence is rejected.

The generator does not accept candidate expected digests.  Verification
reconstructs the expected subject from Git and the receipt, validates both
schemas and self-hashes, and compares canonical bytes.  The subject is written
once with mode `0600`; repository output and overwrite are forbidden.

## Boundary

The generated subject is not a signature, owner identity, authority envelope,
execution capability or live admission.  A successful A4 verification permits
only a separate owner signing review.  It does not read a private key, request
a signature automatically, or unlock side effects.
