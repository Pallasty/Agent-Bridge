# Engram G1 custody cross-implementation differential harness

Date: 2026-07-18

State: `SYNTHETIC_DIFFERENTIAL_OBSERVATION_NO_AUTHORITY`

## Decision

Implement the successor permitted by the custody reconciliation preregistration
as a one-shot public-synthetic observation harness. It leaves both frozen source
profiles unchanged. Rust is exercised through its private feature-gated
test-only permit; Python is exercised through the unregistered isolated lab and
its disposable temporary tree and SQLite double. It adds no MCP, runtime,
production, corpus, key, trust-root, or G1.4 entrypoint.

Every side of every result is explicitly labelled:

- `DYNAMIC` is a newly exercised pinned synthetic behavior.
- `STATIC_WITNESS` is a pinned source finding, not a newly claimed race test.
- `UNRESOLVED_SHARED_GAP` names residual uncertainty instead of inferring
  exclusivity from POSIX modes or link count.

There is no equivalent row. No receipt may select a production control by
taking the strongest property from either implementation.

## Observed asymmetries

The Rust suite rejects raw path spelling, private-parent name rebind,
hard-link-before-open, FIFO/nonregular substitution under a nonblocking open,
final-file rebinding, in-place mutation, and local non-APFS mounts.

The Python lab dynamically accepts a retained session after its private parent
directory has been renamed and replaced, and after that directory's mode drifts
to `0750`; retained file descriptors still validate. It rejects a persistent
hard link, file rebind, byte mutation, and mount-identity drift. Its local
denylist accepts a synthetic local `exfat` mount identity. All successful
Python receipts retain false production and G1.4 fields.

These observations are not vulnerability findings or selected filesystem
policy. They are limited to public synthetic fixture behavior.

## Deliberate residuals

Absolute-ancestor swapping, hard-link open races, Python FIFO timing,
Rust-only metadata mutation, public-artifact name timing, SQLite pathname-open
swapping, and the precommit-to-commit interval remain static witnesses because
the frozen sources expose no safe deterministic interception seam. Creating one
would be a separately reviewed source change.

Darwin ACL and APFS clone/snapshot/backup-alias cases remain explicit
`UNRESOLVED_SHARED_GAP`; neither source proves their absence.

## Verification and boundary

The checker reruns the exact predecessor checker, verifies frozen source hashes,
runs the Rust suite, executes the Python disposable probes twice, and requires
identical redacted receipts. It rejects semantic policy drift below the raw
contract-byte pin.

The next possible work is a separate, reviewed narrow remediation experiment.
This gate grants no real custody, authority, filesystem-policy widening,
descriptor or SQLite VFS change, production promotion, or G1.4 opening.
