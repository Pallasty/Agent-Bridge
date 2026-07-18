# BioCortex Track B S20A: non-live trusted-controller security core

Date: 2026-07-18

Status: **S20A_NON_LIVE_TRUSTED_CONTROLLER_SECURITY_CORE_SYNTHETIC_ONLY**

Decision: **BLOCKED_PENDING_S20B_NON_CYCLIC_RICH_PACKET_CONTRACTS_AND_FULL_BUILDERS_BEFORE_ANY_S21_OWNER_BOUND_LIVE_STAGE**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Outcome

S20A freezes the non-live trusted-controller security core that can be stated
honestly on top of S19. It specifies closed packets for an external
anti-rollback checkpoint, an absorbing one-shot attempt tombstone, an
action-start linearization receipt, and an exact-canary run index. Each packet
has a domain-separated, explicitly test-only synthetic fixture whose self
digest is recomputed over a declared non-cyclic hash scope.

This stage is non-live. Its Rust target is a private, default-off synthetic KAT
kernel. The 14-test targeted replay passed, so the mechanically recorded state
is IMPLEMENTED_S20A_SECURITY_CORE_SYNTHETIC_KAT_PASS_RICH_PACKET_LAYER_BLOCKED.
The four S19 rich-packet full-builder/validator fields remain false. S20A still
cannot accept real authority, create a lab root, launch a child, signal a
process, or collect an observation.

The immediate successor is the non-live
S20B_NON_CYCLIC_RICH_PACKET_SCHEMA_REPLACEMENTS_AND_FULL_VALIDATORS stage. S20B
must replace the cyclic or non-representable S19 rich contracts and implement
their full builders, parsers, and semantic validators. S21 remains only a
future possible live stage, contingent on completed S20B and a newly frozen,
owner-bound subject. An S18 envelope that binds only the earlier S19 subject
cannot authorize code introduced in S20A or S20B.

## Frozen predecessor boundary

S20A consumes but does not modify these S19 schemas:

- agent_bridge.memory_temporal_owned_lab_subject_manifest_s19.v0
- agent_bridge.memory_temporal_owned_lab_preflight_receipt_s19.v0
- agent_bridge.memory_temporal_owned_lab_control_snapshot_s19.v0
- agent_bridge.memory_temporal_owned_lab_authority_control_claim_s19.v0
- agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s19.v0

S20A does not claim full construction or semantic validation of the four rich
S19 runtime packets. Closed-world review found contract defects that prevent an
honest full builder:

- the preflight packet requires a control-snapshot digest while the control
  snapshot freshness object requires the preflight-receipt digest; neither
  schema defines self-field exclusion or a phase-separated previous digest, so
  complete canonical packet digests form a construction cycle;
- the control decision permits DENY_UNKNOWN_OR_ROLLBACK, but claim_view forces
  row_present=true and a complete row, while rollback_detected is forced false;
  a missing claim row, rollback, or unknown read cannot be encoded honestly;
- a failed authority claim permits DURABILITY_FAILURE but simultaneously forces
  affected_rows=0 and unclaimed_state_mutated=false; an acknowledged-unknown
  COMMIT may actually have consumed one row; and
- a successful authority claim forces both durable commit and affine-permit
  issuance true; a crash after database commit but before in-process permit
  minting cannot be represented without lying.

S20B must replace these contracts with non-cyclic, phase-separated digest
definitions and explicit unknown-outcome terminal hard-lock states. Until then,
all four rich-packet full-builder/validator fields remain false. Schema
conformance alone is never authority or evidence.

S20A preserves the exact S17 canary denominator:

| Measure | Frozen target | Observed in S20A |
|---|---:|---:|
| OL00 / OL04 / OL05 attempts | 1 / 6 / 53 | 0 / 0 / 0 |
| Assigned attempts | 60 | 0 |
| pidfd SIGKILL attempts | 59 | 0 |
| Fresh-exec reads | 59 | 0 |
| S16 mapping phases | 113 | 0 |
| Successful live claims | 1 maximum | 0 |

No S17 or S19 artifact is rewritten to contain S20A evidence. All current
fixtures are TEST_ONLY, SYNTHETIC, and NON_LIVE.

## Trusted-controller state machine

The target state machine has no retry edge:

    REGISTERED_UNUSED
      -> ATTEMPT_RESERVED
      -> PREFLIGHT_VALIDATED
      -> CLAIM_ATTEMPT_BURNED
      -> CLAIM_CONSUMED
      -> ACTION_START_LINEARIZED
      -> POSTRUN_TERMINAL

Any failure, crash, missing receipt, unknown checkpoint acknowledgement,
rollback/fork indication, STOP, revocation mismatch, or custody failure enters
an absorbing terminal state. Revalidating an S18 envelope, changing run ID,
challenge, controller process, or capability nonce cannot create another
attempt for the same authorization and claim namespace/key.

The attempt reservation must be durable before preflight. The claim opportunity
must be burned before the S19 CAS is attempted. A failed S19 CAS may leave the
S19 claim row AUTHORIZED_UNCLAIMED, but the S20A attempt tombstone
must still prevent automatic or implicit retry. An unknown durable outcome is a
terminal fail-closed result, not permission to inspect and retry.

## External anti-rollback checkpoint

S19 protects monotonic state only inside the currently verified SQLite database
instance. S20A defines the missing PREPARED -> database commit -> COMMITTED
checkpoint protocol.

The real checkpoint provider is deliberately absent from S20A. A digest, counter,
or second file stored in the same database, directory, filesystem, or
rollbackable failure domain is not independent. A future S21, only after S20B,
must name and bind a real
out-of-band monotonic CAS provider, its identity, policy, current committed
checkpoint, and acknowledgement semantics. Missing, stale, forked, PREPARED, or
acknowledgement-unknown state must hard-lock the authorization without retry.

The synthetic S20A checkpoint fixture tests packet shape and digest handling
only. Its independent_failure_domain_proved field is forced false. It is not an
anti-rollback guarantee, owner decision, registration, or execution capability.

The private KAT adapter does bind the complete prepared token (database
identity, schema digest, next generation, and next logical head), re-reads the
defensive SQLite PRAGMA profile at each checkpointed transaction boundary, and
rejects non-singleton ledgers, incomplete attempts, and pending action intents
on reopen. Its logical head authenticates ordered transition intents; it does
not authenticate every current business-table row or the complete database
file. Full database-content authentication (for example, a checkpointed Merkle
root) remains false and is required before any live successor. The test file's
parent-directory durability is likewise not a real durability adapter.

## Action-start linearization

A post-claim control recheck followed by a returned guard leaves a scheduling
gap. The target S20A API therefore keeps the writer lock while it:

1. reads the exact consumed claim, current revocation epoch, and absorbing STOP;
2. commits a durable action intent for the exact action ordinal;
3. invokes a sealed synthetic adapter inside the controller-owned scope; and
4. records the action-start outcome without returning a serializable or
   cloneable permit.

The action permit is consumed by value. Only a successful outcome returns the
next permit; every error path destroys the input token. Before inserting action
`i`, the journal must contain exactly the complete STARTED prefix `0..i-1`, with
no pending, failed, duplicate, skipped, or future entry. The 60th successful
synthetic start enters POSTRUN_TERMINAL, but this is not a full S19 rich
post-run receipt.

S19 contains no independently authorized assignment membership or operation
descriptor. S20A therefore rejects arbitrary caller assignment IDs and derives
one deterministic synthetic binding from the authenticated manifest and run
ID. That binding is explicitly not proof that an operation belongs to an
owner-authorized assignment. Exact assignment membership remains false and is
an S20B admission requirement.

The S20A adapter is synthetic only and records zero live invocations. A future
real S21 adapter, after S20B, must be newly frozen and owner-bound. STOP and
action start must share
one ordering domain: if STOP linearizes first, the action is denied; if action
start linearizes first, that exact action may start and the next boundary must
observe STOP.

## S20A schema and semantic-validation boundary

Each new S20 packet declares SHA-256, restricted canonical JSON, a distinct
digest domain, length-prefixed framing, the exact top-level self-hash field, and
the rule that this self field and the repository terminal LF are excluded from
the digest payload. The synthetic fixtures contain recomputed digests, not
64-hex placeholders. A one-byte payload mutation must fail digest verification.

The schemas enforce synthetic-state equivalence, complete checkpoint-state
transitions, state-consistent tombstone counters and permits, a declared
operation-bearing action-intent derivation shape, and exact valid-run counts.
JSON Schema cannot recompute that intent or compare two
arbitrary digest-valued fields or independently prove a failure domain, so every
packet also declares cross_field_semantic_validation_required=true and
self_reported_match_fields_are_authoritative=false.

For VALID_COMPLETE_EXACT_CANARY_EVIDENCE, the run index requires exactly 60
action-start receipts and live_action_count=60. This is one start receipt for
each of the 60 assigned attempts. It is explicitly not the number of internal
operation calls made by CREATE, SQLite setup, pidfd, fresh-exec, receipt-write,
or cleanup helpers.

The honest S20A boundary is per-packet schema validation plus an independent
self-digest checker for the four synthetic fixtures. The fixtures are separate
shape KATs; their parent fields do not form an actual mutually bound receipt
chain. S20A therefore does not claim runtime full-packet builders, cross-packet
binding recomputation, full rich S19 packet construction, or the S17 32-rule
validator over the frozen 5,639-row catalog. Those implementation booleans stay
false and those responsibilities move to S20B.

All reservation, checkpoint, attempt, and action handles remain private,
non-Clone, non-Copy, and non-serializable. Error paths consume input tokens and
return no capability.

## Synthetic versus real inputs

The S20A synthetic path must require all of the following:

- test_only=true;
- synthetic=true;
- a SYNTHETIC_KAT_NON_LIVE state;
- domain-separated synthetic identifiers;
- zero live counters; and
- side_effects_unlocked=NONE.

The target real path must reject every S20A synthetic fixture, known test key,
placeholder digest, candidate-supplied expected binding, create-on-demand
ledger, and same-failure-domain checkpoint. No real path is present in S20A.

The following remain absent:

- real owner identity and owner signature;
- real independently installed owner trust anchor;
- real external anti-rollback checkpoint provider;
- real AUTHORIZED_UNCLAIMED registration;
- real preflight observer;
- real runner or side-effect adapter;
- real claim, affine permit, action start, lab root, process signal, observation,
  cleanup, or custody record; and
- provider, production, currentness, admission, output, or application authority.

## Safety and claim ceiling

Network, credentials, paid resources, privilege escalation, mount/unmount,
drop-caches, reboot, kernel crash, power fault, direct block-device mutation,
numeric-PID fallback, named control IPC, descendants, provider access,
production access, Bridge, StateStore, and Agent-Bridge application side effects
remain forbidden.

Even a future complete S21 canary can claim at most:

OWNED_LAB_LOCAL_PROCESS_DEATH_RECOVERY_L1_ONLY_NOT_HOST_POWER_LOSS_NOT_STORAGE_DEVICE_DURABILITY_NOT_PROVIDER_DURABILITY_NOT_ROLLBACK_RESISTANCE

Valid evidence is not necessarily a favorable scientific result. A complete
negative result may still be valid evidence. S20A itself has zero observations
and makes no runtime or durability claim.

## S20B successor and future S21 boundary

The immediate successor is
S20B_NON_CYCLIC_RICH_PACKET_SCHEMA_REPLACEMENTS_AND_FULL_VALIDATORS. It is
non-live, not preapproved, and may unlock no side effect. It must:

1. replace the four cyclic or non-representable S19 rich packet contracts;
2. define phase-separated parent and self-digest scopes;
3. represent missing rows, rollback, unknown reads, unknown COMMIT outcome, and
   post-commit/pre-permit crash without self-contradiction;
4. implement full builders, parsers, digest and cross-binding recomputation;
5. implement the S17 32-rule validator over all 5,639 frozen rows without an
   assignment prefilter; and
6. bind exact authorized assignment membership and concrete operation
   descriptors instead of trusting a caller-provided assignment label;
7. authenticate the relevant database contents with a committed content root or
   prove an equivalently closed sole-writer boundary; and
8. pass negative schema mutation, digest tamper, transition, and crash-cut KATs.

Only after completed S20B may a separately reviewed S21 be considered. That
future stage must freeze the final integrated S20A/S20B source, commits, trees,
binaries, toolchains, feature set, and validator rulesets; obtain a new
canonical subject and owner signature binding all additions; and independently
provide the real trust anchor, checkpoint provider, external registration,
observer, runner, exact canary, receipt chain, retention, cleanup, custody, and
review inputs. S21 is not preapproved by S20A.

Changing S20A/S20B code, schemas, rulesets, binaries, or build inputs after
owner signing invalidates the subject and requires a new manifest and owner
decision.
