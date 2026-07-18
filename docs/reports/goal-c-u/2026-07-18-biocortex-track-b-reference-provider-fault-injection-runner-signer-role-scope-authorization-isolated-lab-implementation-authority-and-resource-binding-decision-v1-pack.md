# Track B signer role/scope authorization isolated-lab implementation authority and resource-binding decision v1

Date: 2026-07-18

## Outcome

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY`

The owner's direction to continue records one exact, bounded, reversible local
implementation decision:

`AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED`

The decision authorizes only the next public-only synthetic T06 verifier unit.
It does not implement that unit. It does not authorize production signer
authorization, real owner or subject identity, action or resource capability,
provider access, runtime registration, evidence ingestion, a runner, a fault,
deployment, output, or a downstream claim.

The exact successor is:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_CLASS_TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

This decision is inert on source and fast replay. Only an ordinary two-parent
integration followed by the full replay gate can make its new single-use
implementation authority effective. The decision gate does not consume the
authority; only the exact successor's later integrated full gate may consume
it.

## Why the scope is exactly six dimensions

The upstream T06 prerequisite says to authorize an authenticated signer to the
exact owner class, evidence class, track, subject, audience, and nonce scope.
Those are therefore the complete request scope in this unit:

1. `owner_class`;
2. `evidence_class`;
3. `track_id`;
4. `subject`;
5. `audience`; and
6. `nonce_scope`.

The decision deliberately does not add `action` or `resource`. Neither field
is defined by the upstream T06 semantic specification, and introducing them
would silently create a capability vocabulary, resource namespace, hierarchy,
or parent/wildcard policy that this evidence chain has not grounded. The source
therefore freezes both
`ADD_ACTION_OR_RESOURCE_CAPABILITY_AUTHORIZATION` as a forbidden operation and
`action_or_resource_capability_authorized=false` as a nonclaim.

The implementation resource binding described later in this report concerns
local CPU, memory, worktree, scratch, network, credential, and spend limits. It
must not be confused with authorization over a production resource object.

## Authority planes and owner-label semantics

| Plane | State after the decision integrated full gate | Meaning |
|---|---|---|
| Planning direction | `ISOLATED_LAB_FIRST` | Continue the next bounded offline unit |
| Exact implementation unit | `AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT` | One non-transitive, single-successor local authority |
| Runtime / provider / production | not authorized | No endpoint, credential, evidence, execution, activation, or production signer authority |

The predecessor T05 implementation authority is already
`CONSUMED_SCOPE_COMPLETE` and cannot be reused. The new authority is
default-off, non-transitive, non-delegable, and limited to reversible local
code, schemas, fixtures, tests, documentation, checker, report, and source-bound
gate work for the named successor.

The semantic implementation actor label is `pallasting`, with role
`PROJECT_OWNER`, based on the established project profile and current-session
continuity. This is not cryptographic identity authentication: no signature or
identity proof was observed, and runtime owner identity and decision remain
unbound. External paid spend is zero in every currency. Zero is a fail-closed
default under reversible autonomy, not an owner-supplied budget reservation.

## Six-input topology and mandatory review order

The future public API has exactly six disjoint inputs, in this order:

```text
frame
detached_authentication_bundle
separately_injected_synthetic_trust_policy
separately_injected_synthetic_signer_authorization_policy
detached_authorization_request
mode
```

The review sequence is frozen as:

```text
MODE_PREOBSERVATION_GUARD
T05_BOOTSTRAP_TRUST_AUTHENTICATION_REVIEW
SEPARATE_SIGNER_AUTHORIZATION_POLICY_REVIEW
DETACHED_AUTHORIZATION_REQUEST_REVIEW
```

`PRODUCTION` and every unknown mode must reject before any of the other five
inputs is observed. In the exact synthetic mode, the verifier must call the
frozen T05 public reviewer exactly once on a successful path. It may not accept
a caller-supplied T05 receipt.

The signer authorization policy is separately injected. It may not be derived
from, embedded in, or aliased with the frame, authentication bundle, or
authorization request. The request is observed only after the separate policy
has passed its bounded closed-world review.

## T05 identity tuple is the only signer-identity source

Signer identity is derived only from the successful T05 predecessor receipt.
The future verifier binds the following mappings:

| T06 profile field | Required T05 receipt source |
|---|---|
| `signer_key_id` | `active_leaf_key_id` |
| `signer_key_version` | `active_leaf_key_version` |
| `signer_role` | the equal `mapped_policy_leaf_role` and `track_leaf_role` |
| `declared_role_class` | `declared_role` |

The authorization profile also freezes the T05 frame SHA-256, trust-policy
SHA-256, public vector-set identifier, revocation-snapshot revision, and exact
T05 receipt content SHA-256. These values are synthetic KAT bindings, not
provider currentness or production trust assertions.

The detached authorization request is forbidden from supplying
`declared_role_class`, `predecessor_receipt_content_sha256`, `signer_key_id`,
`signer_key_version`, or `signer_role`. Consequently a caller cannot replace
the T05-derived identity tuple with self-asserted signer metadata.

## Closed-world default-deny model

The synthetic registry contains exactly two ordered `ALLOW` profiles: managed
first and self-hosted second. Its default effect is `DENY`; explicit deny grants
are not admitted. Authorization succeeds only when exactly one frozen profile
matches both the T05-derived identity/binding fields and all six request-scope
fields by exact ASCII byte equality.

Zero matches and multiple matches both reject. Wildcards, prefixes, parent or
hierarchical matching, role inheritance, group inheritance, implicit grants,
and cross-track substitution are forbidden. The only positive future component
state is:

`AUTHORIZED_SYNTHETIC_KAT_SIGNER_FOR_EXACT_FROZEN_ROLE_SCOPE_COMPONENT_ONLY`

That state is component-local and cannot be promoted to evidence acceptance,
runtime admission, output authorization, or production mitigation.

## Frozen managed and self-hosted profiles

Both profiles share:

```text
effect              = ALLOW
declared_role_class = SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY
owner_class         = SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1
evidence_class      = SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT
trust_policy_sha256 = 882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0
```

Managed profile:

```text
grant_id                       = KAT_MANAGED_SIGNER_ROLE_SCOPE_GRANT_V1
authorization_policy_revision = KAT_MANAGED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1
signer_key_id                   = KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2
signer_key_version              = KAT_MANAGED_LEAF_KEY_VERSION_2
signer_role                     = KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER
track_id                        = MANAGED_SPANNER_CLOUD_KMS
subject                         = KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1
audience                        = AB_TRACK_B_MANAGED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_AUTHORIZATION_KAT_V1
nonce_scope                     = KAT_MANAGED_SIGNER_ROLE_SCOPE_NONCE_V1_0001
frame_sha256                    = e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295
predecessor_receipt_content_sha256 = 46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803
revocation_snapshot_revision    = KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1
vector_set_id                   = KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1
```

Self-hosted profile:

```text
grant_id                       = KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_GRANT_V1
authorization_policy_revision = KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1
signer_key_id                   = KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2
signer_key_version              = KAT_SELF_HOSTED_LEAF_KEY_VERSION_2
signer_role                     = KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER
track_id                        = SELF_HOSTED_ETCD_OPENBAO
subject                         = KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1
audience                        = AB_TRACK_B_SELF_HOSTED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_AUTHORIZATION_KAT_V1
nonce_scope                     = KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_NONCE_V1_0001
frame_sha256                    = da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e
predecessor_receipt_content_sha256 = 72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1
revocation_snapshot_revision    = KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1
vector_set_id                   = KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1
```

All values are non-secret public KAT labels. Managed and self-hosted critical
identity, track, subject, audience, nonce, receipt, vector, and revocation
values must remain disjoint. Their names do not bind a real cloud, provider,
namespace, tenant, owner, subject, or audience.

## Resource binding

Allowed implementation resources are existing local CPU and memory, one
isolated Agent-Bridge worktree, committed non-secret public-only fixtures, and
private local test scratch. The reference component is limited to the Python
standard library and may not fetch dependencies.

The frozen component limits are:

- one worker;
- one T05 predecessor review call per successful review;
- 67,108,864 bytes of private scratch at each checkpoint;
- frame: 1,048,576 bytes;
- detached authentication bundle: 65,536 bytes;
- separately injected trust policy: 65,536 bytes;
- separately injected signer authorization policy: 65,536 bytes;
- detached authorization request: 16,384 bytes;
- JSON depth 32, nodes 4,096, object members 256, and array items 64;
- exactly two authorization grants; and
- each scope string at most 256 UTF-8 bytes, with frozen profile values exact,
  trimmed, ASCII, non-empty, and wildcard-free.

Runtime network, provider endpoints, credential handles and paths, ambient or
system trust, real evidence input, private keys, seed material, signing, key
generation, custody, replay ledger, and trusted production time are forbidden
or bound to `NONE`. Effective external paid spend remains zero.

## Authority lifecycle

The closed-world states are:

```text
UNRECORDED_NO_AUTHORITY
  -> AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT

UNRECORDED_NO_AUTHORITY
  -> REJECTED_FAIL_CLOSED

AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT
  -> CONSUMED_SCOPE_COMPLETE

AUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT
  -> INVALIDATED_REQUIRES_NEW_DECISION
```

A source or fast replay reports no effective authority. An integrated full
decision replay may activate the exact authority but does not consume it. The
transition to `CONSUMED_SCOPE_COMPLETE` occurs only when the exact authorized
T06 successor is integrated and its own full gate passes.

Owner revocation or drift in baseline, unit identity, six-field scope, either
profile, T05 binding, policy separation, input order, allowed operations,
resource caps, reviewer topology, network, credentials, endpoints, or side
effects invalidates the authority and requires a new decision. Global
single-use is not claimed to be proved by an external ledger.

## Truth boundary

The six request values are equality-bound synthetic labels, not claims about
the external world:

- `owner_class` is not an authenticated owner identity;
- `evidence_class` is not a production evidence taxonomy decision;
- `track_id` is not provider-profile, namespace, configuration, or currentness
  proof;
- `subject` is not end-to-end source/build/session/channel/row-set binding;
- `audience` is not an authenticated runtime consumer; and
- `nonce_scope` is fixed public KAT equality only, not generation, freshness,
  uniqueness, single use, expiry, durable replay CAS, or replay protection.

T07 track/profile binding, T08 end-to-end subject binding, and T09 replay CAS
remain unimplemented. No action/resource capability, output permit, evidence
acceptance, runtime admission, provider call, runner launch, fault injection,
scientific claim, or application claim is authorized.

The decision adds zero candidate components and exercises zero new threat
specifications. Its T05 predecessor has three isolated-lab components and
locally covers T01-T05. The authorized future successor may bring the local
total to four components and T01-T06, but that result cannot be claimed until
the successor is implemented and passes its own gates.

Production accounting remains:

- production ingestion controls implemented/runtime-exercised: `0 / 14`;
- production threat specifications runtime-exercised: `0 / 20`;
- runtime prerequisites satisfied: `0 / 16`;
- real, validated, or accepted evidence items: `0`;
- downstream gates authorized: `0 / 4`;
- runtime owner identity, decision, readiness, and admission: false;
- runtime/provider authority: false; and
- runtime side effects unlocked: `NONE`.

## Reviewer and validation topology

The decision source is a pure in-memory closed-world reviewer. It performs no
filesystem, environment, clock, process, network, provider, credential,
randomness, signing, key-generation, or mutable-global-state I/O. It emits a
domain-separated, content-derived scalar receipt.

The independent checker must reconstruct the expected record and receipt
without trusting source helpers, load JSON duplicate-safely with finite bounds,
rederive all section hashes, verify the exact predecessor bytes and T06
semantic-specification binding, mutate every closed-world leaf and hash, reject
overclaims, and inspect source AST purity. Normal output must be stable across
frozen hash seeds; self-test output and counts are separately frozen.

The future implementation requires at least two independent read-only reviewer
lanes after its bytes are frozen:

1. `CONTRACT_CONFORMANCE_REVIEW`; and
2. `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`.

Lane identities must be distinct. No production security reviewer is bound,
and neither lane constitutes production security approval or owner handoff.

## Git and integration topology

The logical baseline is the exact T05 integration
`7df72e2d49bbc25580d4dcb63bc1a183120bba77`, tree
`7fc4786b814d81d97e8672bcae484c07e180f04a`, with parents
`2707996e0616885fa51da9b908764f017a67299f` then
`2a26de5b99886922240350fadefa07bc8f4c5dcd`.

The decision source commit must have that baseline as its exact sole parent and
must be an all-add seven-path packet: reviewer source, independent checker,
owner decision JSON, expected TSV, manifest, report, and executable gate. An
ordinary integration has exactly two parents: a first parent descended from the
baseline that does not already contain the source, and the immutable source
commit as second parent.

Fast-forward release, squash, rebase-shaped history, octopus merge, replace
refs, grafts, alternates, executable Git filters, attribute substitution,
symlink/hardlink substitution, index flags, file-mode drift, dirty worktree, or
protected-byte substitution fail closed. Fast replay is non-release content
identity evidence. Full replay is release evidence and is permitted only on the
ordinary two-parent integration.

The gate archives the protected seven-path packet, checks exact Git objects and
modes, and uses one isolated sparse checkout at the frozen T05 integration to
replay the exact predecessor gate. The predecessor fast receipt is 95 lines
with SHA-256
`3881e2fbeacfa584098233cae7f7b8cbb56e4f5abb6d7dfb7c75fc59420b7f1b`;
the predecessor full receipt is 96 lines with SHA-256
`baf76dca1f7ff58da7c352665b88ef39503a5765d102f885d29777a3c7d1e0ed`.
Only the full predecessor replay can prove that T05's implementation authority
is consumed before this decision authority becomes effective.

The 64 MiB scratch value is a checkpoint cap on the current gate tree, not a
filesystem quota or a global aggregate across nested predecessor gates.

## Rollback

Before publication, rollback is deletion of the isolated worktree and branch.
After publication, rollback is an ordinary Git revert of the exact source or
integration change. No runtime disable, secret cleanup, provider rollback, or
production kill switch applies because the decision authorizes none of those
states. Scope drift or revocation requires a new decision rather than mutation
of the recorded authority.

## Artifact binding

The following exact lowercase SHA-256 values bind the decision artifacts:

- Reviewer source: `3cd07ed34e3aa9a9b6933ccba69a2da1f20c302c5e7f510f13e539b326f16db5`
- Independent checker: `18cb9e5d8eb63c5bbc0d930035923504b9a3efb89df67dbbf5741aba3cbc10e7`
- Owner decision record: `ba9bf671ec4985c14089e6e68b0bda5a09c0b4b09df1582ba6b8305f5fee4ee6`
- Frozen expected TSV: `6da905a6d05660647ba92b9acf1d494fa277f66bc31b6d0afa07faef9e9e7d45`
- Pack manifest: `95185cd5a0f7f7fc1b49c1ac92c17cdd6b90dddcf3d00b9251e3ae7832bb8f82`

Frozen upstream bindings:

- T05 schema: `d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c`
- T05 reviewer: `f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341`
- T05 checker: `bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20`
- T05 synthetic fixture: `31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e`
- T05 expected TSV: `0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36`
- T05 manifest: `bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b`
- T05 report: `9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0`
- T05 gate: `aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061`
- T05 decision-pack receipt content: `899a27ce565d0a8159334513edba2c166b6b6d56f8b74587a6d5e89be6408715`
- Upstream T06 semantic fixture: `3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`

## Nonclaims

The machine-readable record explicitly denies production signer
authorization, production owner/evidence/track/subject/audience/nonce binding,
action or resource capability, provider/profile currentness, owner identity,
audience identity, subject truth, nonce freshness or replay protection,
production policy status, evidence acceptance, output, runtime admission,
runner launch, fault injection, deployment, provider access, credentials,
trusted time, custody, scientific/application claims, production security
approval, and derived Git publication authority.

It also denies that this decision itself implements T06, T07, T08, or T09; that
the local T06 KAT would be a production mitigation; that global single use is
proved; or that zero spend is a reserved owner budget.
