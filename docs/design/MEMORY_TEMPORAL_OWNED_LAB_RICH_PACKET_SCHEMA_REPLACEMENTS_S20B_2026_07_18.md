# BioCortex Track B S20B: non-cyclic rich packets and full-validator contract

Date: 2026-07-18

Status: **S20B_NON_LIVE_RICH_PACKET_VALIDATORS_COMPLETE**

Decision: **S21_BLOCKED_PENDING_FINAL_REFREEZE_NEW_OWNER_SIGNATURE_AND_INDEPENDENT_LIVE_INPUTS**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Scope

S20B replaces, without modifying, the four frozen S19 target-only rich-packet
contracts for preflight, control snapshots, authority-control claims, and the
post-run receipt bundle. The S19 schemas and all S20A artifacts remain historical
and unchanged. The replacement schemas are closed Draft 2020-12 contracts with
no external references, no floating-point values, and no candidate-authoritative
match booleans.

The private, default-off S20B feature now implements full typed Rust builders,
closed restricted-canonical parsers, digest and parent recomputation, exact
owner-bound assignment membership, typed concrete-operation descriptors,
authenticated SQLite business-content roots, and the S17 32-rule validator over
the complete 5,639-row catalog. Its positive and negative KATs are synthetic and
non-live. No current packet, fixture, feature, token, or status is owner
authority, scientific evidence, or a side-effect capability.

The implementation intentionally has no live observation constructor, no live
CAS-transition adapter, no independent checkpoint provider, no live nested
receipt constructor, and no executor. Production-success variants require
opaque evidence that none of the synthetic fixtures can construct. Therefore
`side_effects_unlocked=NONE` remains the enforced boundary.

## Non-cyclic receipt graph

The only permitted parent direction is:

    owner-bound assignment and operation descriptors
      -> registration and durable attempt reservation
      -> preflight context
      -> PREFLIGHT_BEFORE_CLAIM control snapshot
      -> final preflight receipt
      -> CAS_LINEARIZATION control snapshot
      -> claim transition core
      -> committed database-content root
      -> external checkpoint commitment
      -> claim and process-local permit outcome
      -> ordered action-start receipts
      -> raw observations and post-run receipt chain
      -> post-run bundle

The preflight context digest covers authority, run, build, assignment,
operations, environment, registration, checks, and freshness. It excludes both
the later control snapshot and final preflight self digest. A preflight-phase
control snapshot binds that context digest and MUST NOT bind the final preflight
receipt. The final preflight receipt then binds the context and snapshot. Later
control phases may bind the completed preflight or claim receipt. No packet may
refer to a descendant or derive a content root from its own self digest.

Database rows commit a phase-separated transition-core digest. The authenticated
database-content root covers the four fixed business tables, fixed ordered
columns and primary-key order, explicit SQLite NULL/integer/real/text/blob type
frames, schema-catalog digest, database identity, and generation. Every
committed-state token recomputes this root and matches an external checkpoint;
same-connection and reopen checks also re-read the exact application ID, user
version, journal mode, and defensive SQLite profile. A final claim receipt may bind that root, but
its own digest is not an input to the root it cites. If a final receipt is later
stored, that storage is a new backward-linked, separately checkpointed
transition. The independently recomputed initial synthetic-ledger KAT is
`5463bd72d21d1515cebb33c8c575883db86cd12c1a980c878192a9802459e56d`.

## Hash contract

Every top-level replacement packet has:

- SHA-256;
- AB restricted canonical JSON S20B v1, compact with sorted keys, ASCII values,
  and no floating-point numbers;
- a packet- or variant-specific domain;
- U32BE domain-length and U64BE canonical-payload-length framing;
- exactly one named top-level self-hash field excluded from the payload;
- exclusion of the repository terminal LF only;
- cross-field semantic validation required; and
- all self-reported match fields treated as non-authoritative.

Nested post-run receipts also have distinct domains, explicit parent hashes, and
self-field exclusion. Validators consume canonical parent packet bytes and
recompute hashes; they never accept a candidate-supplied expected digest.

The preflight-context component profile hashes the exact canonical value of each
named top-level component with
`agent-bridge/biocortex/owned-lab/s20b/preflight-context-component/<component>/v1`,
where `<component>` is one of `authorization-binding`, `run-binding`,
`assignment-binding`, `build-binding`, `environment-snapshot`,
`claim-registration`, `checks`, or `freshness`. The context digest then hashes
the exact canonical `preflight_context` object with the declared
`agent-bridge/biocortex/owned-lab/s20b/preflight-context/v1` domain and the same
length framing.

The claim transition core has one exact, non-self-referential construction.
Its domain is
`agent-bridge/biocortex/owned-lab/s20b/claim-transition-core/v1`. The message is
`U32BE(domain length) || domain`, followed by 24 U64-length frames in this
order: the ASCII `parameter_order_profile`, then `p01` through `p24` with
`p06_claim_transition_core_sha256` omitted. The five scalar parameters `p01`,
`p13`, `p14`, `p19`, and `p20` are U64BE; every other included `pNN_sha256`
parameter is its decoded 32-byte digest. The final claim self digest, database
content root derived from that transition, and checkpoint receipt are not
inputs. This fixture profile recomputes p06 as
`6f2ceefbcac65a1bf64b23edee917e9346417922b1880f064e1347b6b1546f6f`.

Four compact, sorted, ASCII-only, test-only synthetic KAT packets accompany the
schemas. Their digests are non-placeholder values recomputed in parent order:
context, preflight-phase control snapshot, final preflight, claim outcome, then
post-run bundle. They deliberately carry no authority, permit, runtime
observation, scientific evidence, or side-effect capability.

## Frozen assignment and operation ABI

The production assignment validator reconstructs exactly 60 one-based records:
one OL00, six OL04, and 53 OL05 records, totaling 113 phases. It never treats a
caller label as membership. The owner-bound token carries the authorization ID,
owner envelope, subject manifest, resource scope, capability nonce, assignment
set, and schedule. Every consuming validator rechecks that complete tuple.

Concrete operation operands use a closed typed ABI: `BOOLEAN`,
`UNSIGNED_INTEGER`, `OCTAL_MODE`, `RELATIVE_PATH`, or `SYMBOL`. Each operand is
canonical JSON with explicit `name`, `type`, and typed `value`; all operation,
operation-set, record, schedule, and set hashes use the frozen S20B v2 domains.
Independent KAT values are:

- assignment set: `b3a7025a488e9aefc6724869f75ab76a482002224bee90c075e9379101ee7264`;
- schedule: `8c0129d150d918523c122dbf3afb4e7c6abb3ce7ca957204252c115a7f1def15`;
- record set: `7a927eba7eb691990b32c7987bea5c0fdce15c51d37792f8ca45c3bddb556bc6`;
- global operation set: `a00feb5745c83fc20d5ad84f66877289c9108b29371697ceb8cf13e3fb142db0`;
- first/last records: `b9e38d17c7d6974b7fb49e0840bf2e431f60dc8bc309c31b6202c3b5bcbf41fc`
  and `6bd2c6e3648030d1de1a3be795a6ad221887fc8e273c9c771024d85b9866f135`;
- OL00/OL04 operation sets: `341fa260fcc7958e18891f4143fd33bcafb13efcfd6f4fd07a16058be16a654b`
  and `e6cc4cfe754e3d3e9b0e670cfdfb38ce065e4bf2ec157c092ae8bf75da586e94`.

The four repository fixture packets deliberately retain their own synthetic
placeholder assignment commitments and `membership_validated=false`. They test
schema and digest mechanics only; they cannot produce the owner-bound
assignment token and are rejected by every production-success path.

## Repaired packet states

### Preflight

The packet carries complete authorization, run, build, assignment, concrete
operation-plan, environment, independent registration, checks, freshness,
content-root/checkpoint, context, and control-snapshot bindings. READY is valid
only when every independent check succeeds. Failure and unknown outcomes are
absorbing and permit no CAS or retry.

### Control snapshot

Claim, STOP, and revocation views are tagged. Claim may be present, missing, or
unknown. STOP may be clear, triggered, or unknown. Revocation may be exact,
mismatched, rollback-detected, or unknown. Revisions and row digests are absent
when they were not observed. ALLOW requires a complete present row, current
content root and independent checkpoint, clear STOP, exact revocation, and an
exact backward phase parent. Missing, rollback, and unknown states hard-lock.

### Authority-control claim

The schema distinguishes registration, ledger-row, and claim-outcome packets.
The claim outcome binds all 24 SQL parameters plus attempt, assignment,
operation-plan, content-root, and checkpoint state. Its terminal outcomes are:

- KNOWN_NOT_COMMITTED_TERMINAL;
- COMMITTED_PERMIT_ISSUED;
- COMMITTED_PRE_PERMIT_CRASH_TERMINAL; and
- UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK.

An unknown COMMIT acknowledgement has unknown affected-row and mutation values,
not fabricated zero/false values. A known committed row is distinct from actual
process-local affine-permit issuance. Every non-success path forbids retry.

### Post-run bundle

The bundle binds the exact assignment and operation sets, one successful claim,
the ordered 60 assigned-attempt action-start receipts, raw observations, 113
phase records, final content root/checkpoint, and the retention, semantic, batch,
optional STOP, cleanup, and custody chain. VALID_COMPLETE_EXACT_CANARY_EVIDENCE
requires exact counts 1/6/53, 60 assigned attempts, 59 pidfd SIGKILL attempts,
59 fresh-exec reads, 113 phase records, 60 observations, 60 assigned-attempt
start receipts, one successful claim, and zero retries.

The full S17 32-rule semantic validator must search all 5,639 frozen catalog rows
for every classification. Assignment family, case, and variant are forbidden as
prefilters. Zero or multiple matches are retained as indeterminate. Valid
evidence does not imply a favorable scientific result.

## Completed mechanical gate

S20B mechanical completion requires, and the closed replay verifies, all of the
following:

1. typed full builders and closed parsers for all four replacement schemas;
2. exact canonical-byte and top-level/nested self-digest recomputation;
3. the complete backward-only parent graph and immutable identity-tuple checks;
4. all tagged missing, rollback, unknown-read, unknown-COMMIT, and
   post-commit/pre-permit-crash outcomes;
5. full 24-parameter claim predicate validation;
6. exact canonical assignment-set membership and concrete operation descriptors;
7. an authenticated committed database-content root, or an independently proved
   equivalently closed sole-writer construction;
8. the exact S17 32-rule validator over all 5,639 rows without label prefilter;
9. one coherent synthetic cross-packet chain with recomputed non-placeholder
   hashes; and
10. negative schema, canonicalization, digest, identity, assignment, operation,
    parent, transition, content-root, checkpoint, and crash-cut KATs.

The frozen S19/S20 commits and their historical receipts are not rewritten.
S20B extends the current S20 parent source with content-root verification and
records completion only in new S20B artifacts.

## Future S21 boundary

S20B is non-live, not preapproved, and unlocks no side effect. Even completed
S20B only makes S21 separately reviewable. A future S21 must freeze final
integrated S20A/S20B commits, trees, source, binaries, toolchains, feature set,
schemas, assignment set, operation descriptors, catalog, and validator rulesets.
It then requires a new canonical subject, a new owner signature, an independently
installed trust anchor, a real independent checkpoint provider, external
registration, a fresh observer, a real runner, exact canary inputs, and complete
retention, cleanup, custody, and review artifacts. The S19 owner envelope cannot
authorize S20A or S20B additions.
