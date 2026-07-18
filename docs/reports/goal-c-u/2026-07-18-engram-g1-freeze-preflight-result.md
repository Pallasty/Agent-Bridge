# Engram G1.1 Freeze-Preflight Result

Date: 2026-07-18

Status: **PASS / INDEPENDENT ROLE ASSIGNMENT ONLY**

## Result

The G1.1 public preflight contract, hash-only role packet validator, and
hash-only private manifest validator pass their deterministic and negative
gates. This resolves the known rate-granularity, comparator, family-cap, salted-
commitment, role-custody, and appointment-before-assembly ambiguities before
any new consumer material is observed.

No real role holder was assigned. No new G1 query, target key, group roster,
application-family membership, partition membership, or sealed material was
read or created. Existing G0 private literals were used only by an in-memory
non-disclosure scan; none appeared in the staged artifacts or tool output.

## Binding

- predecessor commit:
  `d8a17461858354a1b0bbd4f86c29eae75bdf0aa9`;
- predecessor G1 design SHA-256:
  `275ae840b62a8a5408ea11e98836aefded998d87d2a2c4846939414a3128a0f0`;
- G1.1 contract SHA-256:
  `5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a`;
- admitted G0 group-id commitment:
  `5bb20800cea3bdb973ea0604fcd280e89666736b7cd9e595e24c89f4b744a1fc`.

The predecessor files remain unchanged. G1.1 is a successor contract and does
not rewrite v0 evidence.

## Decisive amendment

The future candidate is evaluated on paired sealed episode groups. It must
repair at least two `overgeneralization_gap` groups versus each of
`stable_control` and `density_only`. It may introduce zero new exact misses,
related misses, no-gap regressions, or per-mode unrelated intrusions. Rate
statistics are descriptive only.

This is a deterministic engineering-screen rule. It cannot support a
population-effect, neuroscience-equivalence, product-value, or runtime claim.

## Packet boundary

The role packet requires five distinct salted holder commitments: one
candidate implementer, one consumer curator, two freeze reviewers, and one
sealed evaluator/custodian. It binds distinct appointment-receipt commitments
and a pre-assembly timestamp. The validator checks structural separation but
cannot authenticate the people or appointments.

The manifest binds the exact role-packet bytes and requires an assembly time
strictly after the role packet. It contains salted commitments, provenance
receipts, two identical rank maps per probe, and aggregate integrity evidence.
Real packets must remain untracked under ignored `data/`.

Redacted receipts contain no holder, group, family, query, target, source, or
partition-membership commitments.

## Verification

Passed:

- `scripts/check-engram-g0-failure-intake.sh`;
- `scripts/check-engram-g1-corpus-design.sh`;
- `scripts/check-engram-g1-freeze-preflight.sh`;
- Python compile and Black formatting check;
- `git diff --check`.

The G1.1 checker generated a complete 30-group synthetic manifest with 540
baseline observations. Negative tests rejected contract relaxation, duplicate
or wrongly classified role holders, candidate access, unsalted commitments,
real packets outside ignored `data/`, role-binding and chronology drift,
wrong group or partition structure, G0 movement into sealed, replay drift,
family-cap violation, signature drift, candidate-authored probes, raw query
fields, duplicate query commitments, insufficient sealed-primary groups,
assembly-attestation drift, and duplicate JSON keys.

## Authority boundary

A passing public contract permits only independent role assignment. A
structurally valid real role packet can only enter independent role-commitment
review. A structurally valid real manifest can only enter independent corpus-
freeze review.

The following remain false:

- private corpus assembly authority;
- G1 corpus-freeze authority;
- candidate implementation authority;
- BioCortex experiment execution authority;
- retrieval-order mutation authority;
- live-store write authority;
- runtime promotion authority.

## Next gate

The next action belongs to an independent owner: appoint the five role holders
and review their appointment/independence evidence without exposing sealed
material to the candidate lane. A separate role-review receipt must exist
before private corpus assembly begins.
