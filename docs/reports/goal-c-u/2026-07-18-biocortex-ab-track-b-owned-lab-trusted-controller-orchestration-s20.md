# BioCortex / Agent-Bridge Track B S20A trusted-controller security-core report

Date: 2026-07-18

Status: **S20A_NON_LIVE_TRUSTED_CONTROLLER_SECURITY_CORE_SYNTHETIC_ONLY**

Decision: **BLOCKED_PENDING_S20B_NON_CYCLIC_RICH_PACKET_CONTRACTS_AND_FULL_BUILDERS_BEFORE_ANY_S21_OWNER_BOUND_LIVE_STAGE**

Hash table state: **FINAL_CLOSED_WORLD_BOUND**

## Result

The documentation and JSON portion of S20A defines a non-live
trusted-controller security core. It adds four closed Draft 2020-12 packet
schemas and four canonical TEST_ONLY synthetic fixtures. It does not modify any
of the five S19 schemas.

The private, default-off Rust security core is implemented and its 14 targeted
synthetic KATs pass. The machine state is
IMPLEMENTED_S20A_SECURITY_CORE_SYNTHETIC_KAT_PASS_RICH_PACKET_LAYER_BLOCKED.
The four S19 rich-packet full-builder/validator fields remain false and move to
the non-live S20B successor.

## Closed orchestration contracts

The new checkpoint packet expresses the required PREPARED -> database commit ->
COMMITTED protocol and explicitly records that a same-database or
same-failure-domain checkpoint is not independent.

The one-shot attempt schema models reservation before preflight, claim-opportunity
burn before CAS, and absorbing failure or unknown outcomes. A conforming future
runtime must prevent a new run ID, controller, challenge, nonce, or repeated S18
verification from bypassing the authorization/claim-key tombstone.

The action-start schema requires a declared derivation profile covering the
operation, assignment, action sequence, and previous receipt, plus a fresh
claim, STOP, and revocation decision under one writer ordering domain. A future
semantic validator must recompute the intent rather than trust the declaration.
The S20 fixture invokes neither a
synthetic nor a live adapter.

The exact-canary index binds the fixed OL00/OL04/OL05 denominator. A future
valid-complete packet requires exactly 60 assigned attempts, 59 pidfd SIGKILL
attempts, 59 fresh-exec reads, 113 S16 mapping phase records, 60 observations,
one successful claim, zero retries, and exactly 60 action-start receipts. The
last count means one receipt per assigned attempt, not one per internal
operation call. The S20A fixture records all actual counts and action receipts
as zero and is not a complete cross-packet chain.

## S19 rich packet blocker

S20 reuses, without modification:

- agent_bridge.memory_temporal_owned_lab_subject_manifest_s19.v0
- agent_bridge.memory_temporal_owned_lab_preflight_receipt_s19.v0
- agent_bridge.memory_temporal_owned_lab_control_snapshot_s19.v0
- agent_bridge.memory_temporal_owned_lab_authority_control_claim_s19.v0
- agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s19.v0

Closed-world review found four reasons S20A cannot honestly claim full builders
or validators for these packets:

1. Preflight requires control_snapshot_sha256, while control freshness requires
   preflight_receipt_sha256. With complete packet digests and no declared
   self-field exclusion or phase separation, construction is cyclic.
2. Control permits DENY_UNKNOWN_OR_ROLLBACK, but claim_view forces
   row_present=true and a complete row, and revocation_view forces
   rollback_detected=false. A missing row, rollback, or unknown read has no
   truthful representation.
3. A failed authority claim permits DURABILITY_FAILURE while forcing
   affected_rows=0 and unclaimed_state_mutated=false. If SQLite COMMIT landed
   but its acknowledgement was lost, the real outcome may be one row consumed.
4. A successful claim forces both durable commit and affine_permit_issued=true.
   A crash after commit but before in-process permit minting has no truthful
   packet.

S20B must replace these contracts with non-cyclic, phase-separated digest
scopes; nullable or explicit missing/unknown states; an
UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK result; and a distinction between
permit-eligible-after-commit and actual process-local permit issuance. Until
then the four rich-packet full-builder/validator booleans remain false, as do
runtime full cross-packet binding and the full 5,639-row S17 semantic validator.

## New S20A packet digest boundary

Each of the four new schemas declares SHA-256, restricted canonical JSON, a
unique digest domain, U32BE/U64BE length framing, an exact hash scope, and an
excluded top-level self-hash field. The terminal repository LF is also excluded.
The fixtures contain recomputed self digests:

| Packet | Self digest |
|---|---|
| External checkpoint | `44ca36b2deb4ca37314228b071e9566fb8aee8f0e8637ad92b2152f78efa9f1f` |
| Attempt tombstone | `e2b01560aca81270459cd29be6ad843ad192495b096a1eaf2212a068c7e5f869` |
| Action start | `9dca999090f3c7187926783ae8d87c9791c4ab174361fdbe02b05011c559e3a4` |
| Exact run index | `99a11fabc727d3a1e205ef6baccee752f824300f0b764dc3361535a0821609c1` |

These four independent fixtures are packet-shape and self-digest KATs. Their
parent fields do not bind one another into a real receipt chain. JSON Schema
cannot prove arbitrary cross-field digest equality or checkpoint-domain
independence; the packets explicitly require a later semantic validator and
mark self-reported match fields non-authoritative.

## Implemented security core and explicit ceilings

The private Rust kernel implements durable attempt reservation, preflight
validation, pre-CAS attempt burn, the full 24-parameter S19 claim predicate,
zero-row terminalization, a synthetic PREPARED/database-commit/COMMITTED logical
checkpoint, affine action permits consumed by value, exact STARTED journal
prefix enforcement, same-writer STOP/action ordering, and the exact canary index
validator. Transaction boundaries re-read the defensive SQLite profile;
prepared checkpoint commits bind database identity, schema, generation, and
logical head; reopen rejects cardinality drift, nonterminal attempts, and
pending intents. The 60th successful synthetic action enters POSTRUN_TERMINAL.

Two stronger properties remain explicitly false. First, S19 authenticates no
exact assignment-membership ledger or concrete operation descriptor. S20A
derives a deterministic manifest+run synthetic binding and rejects arbitrary
caller values, but does not call that assignment membership. Second, the
logical checkpoint head orders transition intents but does not authenticate all
current business-table rows or the complete database file. A committed content
root or equivalently closed sole-writer proof is required before live use. The
synthetic post-run transition is also not the repaired rich post-run receipt,
and no real parent-directory durability adapter exists.

## Current authority and execution

| Measure | Current |
|---|---:|
| Real S20A-bound subject | 0 |
| Real owner identities/signatures | 0 |
| Real out-of-band trust anchors | 0 |
| Real independent checkpoint adapters/checkpoints | 0 |
| Real AUTHORIZED_UNCLAIMED registrations | 0 |
| Real preflight observers | 0 |
| Real runners or side-effect adapters | 0 |
| Live CAS claims/permits/action starts | 0 / 0 / 0 |
| Live roots/runner launches | 0 / 0 |
| Assigned attempts/SIGKILL/fresh reads | 0 / 0 / 0 |
| S16 mapping phases/observations | 0 / 0 |
| Provider or production authority | 0 |
| Side effects unlocked | NONE |

All fixtures are TEST_ONLY, SYNTHETIC, and NON_LIVE. Passing their schema or KAT
checks is not owner authentication, independent anti-rollback protection,
registration, execution authority, runtime evidence, currentness, admission, or
an output permit.

## Immediate S20B successor; S21 remains future

The immediate successor is
S20B_NON_CYCLIC_RICH_PACKET_SCHEMA_REPLACEMENTS_AND_FULL_VALIDATORS. It is
non-live, not preapproved, and must implement the repaired contracts, full
builders/parsers/validators, runtime digest and cross-binding recomputation, the
full S17 semantic validator, exact authorized assignment membership and concrete
operation descriptors, authenticated database-content roots (or an equivalent
closed-writer proof), and negative mutation/digest/crash-cut tests.

S21 is only a future possible live stage contingent on completed S20B. It must
freeze the final integrated S20A/S20B source, commits, trees, binaries,
toolchains, feature set, and validation rules. A new canonical subject and new
owner signature must bind every addition. The existing S19 subject cannot
authorize code that did not yet exist, and S20A does not preapprove S20B or
S21.

## Final artifact digest table

This table binds every S20A source artifact other than this report. It contains
exactly 19 unique path/hash rows. Any later edit requires recomputing the
affected digest and re-running the release gate.

| Artifact | SHA-256 |
|---|---|
| crates/store/Cargo.toml | 6c94045720ca77b0a037c9196171960a323f8adadb5d6607b4464eae1d430097 |
| crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization.rs | efcdcc6a656ba069fabdebb91f92dea727a3330cdbd74ccae92b745231f1443e |
| crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner.rs | d9a35534f3c92a9cef3820434cd0bf5ab22c453ca9721712c5c4c595fcea8dc1 |
| crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration.rs | 9c1b1cac42eb541aeb3c566c1356dc0ca66805e9b41304375b22d2e5cdd0bf81 |
| docs/design/MEMORY_TEMPORAL_OWNED_LAB_TRUSTED_CONTROLLER_ORCHESTRATION_S20_2026_07_18.md | 175ffc0564da019af63eb0f880060d3f8366af04c0fee6cff059826f93455de9 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-trusted-controller-orchestration-contract-s20-v0.json | 7f8fb898776228488a5a954f30df4c7de2307462857bd33ddc58966f6b8b1cc4 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-trusted-controller-orchestration-status-s20-v0.json | c47a0af9de7d9fbde88433806b7b205f778268c7c2cd591833a109418677ddae |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-schema-s20-v0.json | f29582a8a23b85d4ed468fdbf003ded727d31b89a899aeac6c5421a889137564 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-synthetic-s20-v0.json | f98d737f329c87344ab87f6984f147b573ce949a5415f9d9d58941b6eba19341 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-one-shot-attempt-tombstone-schema-s20-v0.json | 59eb0bdffaf7426515e1d71539c7e9caf86c2688372955487f60a46a505c01e2 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-one-shot-attempt-tombstone-synthetic-s20-v0.json | f33520cfb7837316cb3931be26fead3990404e81882584c5af6c0910ad1e37d7 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-action-start-linearization-receipt-schema-s20-v0.json | d36e4c1790183fe9cc6535d45dc2fcdd7a6d218c71dea0762641996309e716e0 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-action-start-linearization-receipt-synthetic-s20-v0.json | 646a5e49d7511d411658336d5aec94abfe1dc010e9e0aeba36a4cea5873ed3e3 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-exact-canary-run-index-schema-s20-v0.json | d4e93edeea77db4584812963cbd90cc233ab6ea5964ae176c4db9f3587024452 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-exact-canary-run-index-synthetic-s20-v0.json | 6e2179c33d5875159ce5c969778844db025c695d421dc57feeb423881ac081d6 |
| docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20-v0.json | 037e82da0b45190061457b249b607fdc4b39cdcfa936aaf63021f88cd6d18192 |
| scripts/eval/check_memory_temporal_owned_lab_trusted_controller_orchestration_s20.py | ec08e933d3b6ca628e977e9572ebc9615261bcc3ef3589a671a516e60a8ec852 |
| scripts/eval/fixtures/memory_temporal_owned_lab_trusted_controller_orchestration_s20.expected.v0.tsv | 1fc34caa4f5db26d309f91d836dd75f60f68637d44b125df0574c8bdb848e76e |
| scripts/check-memory-temporal-owned-lab-trusted-controller-orchestration-s20.sh | 6a53c78830296a16ffe2ad8d45f60351807b5719d2f85210fc712b5feb5d1d78 |

## Closed-world validation performed

At finalization:

- every new JSON file parsed successfully;
- each of the four schemas passed Draft 2020-12 schema self-validation;
- each synthetic fixture validated against its corresponding schema;
- each synthetic fixture matched compact recursively sorted JSON plus exactly
  one terminal LF; and
- every synthetic self digest recomputed under its declared domain, framing,
  scope, and exclusion rule, while a one-byte payload mutation changed the
  digest and was rejected;
- adversarial mutations were rejected for synthetic/real state confusion,
  incomplete or non-independent COMMITTED checkpoints, PREPARED-as-current,
  terminal tombstone counter/permit contradictions, denied-action control/start
  contradictions, missing operation/assignment/previous-receipt bindings, and
  valid-complete runs without exactly 60 assigned-attempt start receipts; and
- the private, default-off `ab-store` S20 test filter passed 14/14 tests with
  `-j1`, one Rust test thread, zero measured swaps, and approximately 1.21 GiB
  peak RSS in the targeted replay;
- the independent checker passed its eight targeted negative mutations and
  verified the exact Rust test catalog, parent edits, frozen S19 identities,
  packet self hashes, machine-state boundaries, and false nonclaims; and
- the shell release gate passed static syntax validation and is configured for
  serial, offline, private-archive-only S20 Cargo replay. The frozen S19 chain
  runs through its own clean-environment, offline gates at host namespace level
  so that its root-owned `01777` `/tmp` invariant and nested namespace checks
  remain observable; it is not wrapped in a second user namespace that would
  remap host root to the overflow UID.

These checks complete only the S20A synthetic security core. They do not
establish a real cross-packet receipt chain, complete the S19 rich layer, prove
exact authorized assignment membership, authenticate the full database
contents, or unlock any effect.
