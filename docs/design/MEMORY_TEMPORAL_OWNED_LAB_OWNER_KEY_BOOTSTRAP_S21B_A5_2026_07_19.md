# BioCortex Track B S21B-A5: owner key bootstrap boundary

Date: 2026-07-19

## Decision

The A4 unsigned subject is verified, but an owner authorization payload cannot
be finalized until the owner supplies a public Ed25519 key from an independently
held private key.  The project must not generate, import, inspect or store the
private key.  A5 therefore adds only a public-key inspector and a closed
bootstrap contract.

The inspector accepts an Ed25519 SubjectPublicKeyInfo PEM, derives the exact
32-byte raw public key and SHA-256 fingerprint, and rejects private-key PEMs,
non-Ed25519 keys, trailing data and repository-resident real key files.

After the owner creates the key outside the repository, the next A5 unit may
construct the trust anchor, challenge/capability nonces and exact detached
signature message.  No signature, authority, admission or live side effect is
created by this unit.
