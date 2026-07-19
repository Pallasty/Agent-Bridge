# Track B T07 track/profile binding isolated-lab implementation authority and resource-binding decision v1

Date: 2026-07-18

## Outcome

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_TRACK_PROFILE_BINDING_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY`

The owner's direction to continue records one exact, bounded, reversible local
implementation decision:

`AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T07_TRACK_PROFILE_BINDING_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED`

The decision authorizes only the next public-only synthetic T07 verifier unit.
It does not implement that unit. It does not authorize production track or
subject binding, real provider or lab identity, profile or configuration
currentness, evidence ingestion, runtime registration, a runner, a fault,
deployment, output, or a downstream claim.

The exact successor is:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_TRACK_PROFILE_BINDING_SYNTHETIC_EXACT_PACKET_PROFILE_PROVIDER_OR_LAB_PROFILE_NAMESPACE_CONFIGURATION_SHA256_AND_NON_SUBSTITUTABLE_TRACK_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The decision itself adds zero candidate components and exercises zero new
threat specifications. The released predecessor remains four isolated-lab
components covering T01-T06. Only the later exact successor may raise the
local ceiling to five components covering T01-T07.

This decision is inert on source and fast replay. Only an ordinary two-parent
integration followed by the integrated full replay gate can make its new
single-use implementation authority effective. The decision full gate does
not consume the authority; only the exact successor's later integrated full
gate may consume it.

## Why the scope is T07 track/profile binding only

The frozen 20-threat model separates two adjacent failure classes:

- T07 `TRACK_ISOLATION`: managed/self-hosted packet, profile, namespace, or
  configuration substitution; and
- T08 `SUBJECT_BINDING`: prerequisite, source, build, session, channel,
  schedule, row-set, or subject mismatch.

The production control is named `TRACK_SUBJECT_BINDING`, but that shared
control name does not merge the two threat cases. This unit therefore binds
only the T07 track/profile tuple. It explicitly does not parse the frame again,
observe or match subject, bind prerequisite or build identity, or implement any
part of T08 or T09.

The semantic implementation actor label is `pallasting`, with role
`PROJECT_OWNER`, based on the established project profile and current-session
continuity. The observed direction is
`CONTINUE_NEXT_BOUNDED_T07_TRACK_PROFILE_BINDING_DECISION_UNIT`. This is a
semantic owner label, not cryptographic authentication: no owner signature or
identity proof was observed, and no runtime owner identity or decision is
bound.

## Eight-input topology and mandatory review order

The future public API has exactly eight disjoint inputs, syntactically ordered
as follows:

```text
frame
detached_authentication_bundle
separately_injected_synthetic_trust_policy
separately_injected_synthetic_signer_authorization_policy
detached_authorization_request
separately_injected_synthetic_track_profile_binding_policy
detached_track_profile_binding_request
mode
```

Although `mode` is syntactically last, it is the first input observed. The
review sequence is frozen as:

```text
MODE_PREOBSERVATION_GUARD
T06_SIGNER_ROLE_SCOPE_AUTHORIZATION_REVIEW_EXACTLY_ONCE
SEPARATE_TRACK_PROFILE_BINDING_POLICY_REVIEW
DETACHED_TRACK_PROFILE_BINDING_REQUEST_REVIEW_LAST
EXACT_SINGLE_PROFILE_MATCH
```

`PRODUCTION` and every unknown mode must reject before any other input is
observed. In the exact synthetic mode, the verifier calls the frozen T06 public
reviewer exactly once on a successful path. It may not accept a caller-supplied
T06 receipt.

The track/profile binding policy is separately injected. It may not be derived
from, embedded in, or aliased with the frame, authentication bundle, signer
authorization policy, authorization request, or detached T07 request. The T07
request is observed only after the separate policy has passed bounded
closed-world review.

## Exact six-dimension match and four-field request

The detached T07 request has exactly four fields:

1. `packet_profile_id`;
2. `provider_or_lab_profile_id`;
3. `namespace_id`; and
4. `configuration_sha256`.

The track identity comes only from the successful T06 predecessor receipt.
Each policy profile additionally freezes that track's exact T06 receipt content
identity. The complete policy match is therefore exactly six dimensions:

```text
t06_receipt_content_sha256
track_id
packet_profile_id
provider_or_lab_profile_id
namespace_id
configuration_sha256
```

The request must not contain `track_id`, `subject`, `prerequisite_id`,
`build_id`, the T06 receipt or receipt hash, frame hash, declared role, or
signer key/version/role fields. Track identity cannot be supplied by the T07
request or re-derived from the raw frame.

The two ordered policy profiles are managed first and self-hosted second.
Every field matches by exact ASCII byte equality. Zero matches and multiple
matches reject. Wildcards, prefixes, hierarchical or parent matching, role or
group inheritance, implicit grants, and cross-track substitution are
forbidden. The only successful future component state is:

`BOUND_SYNTHETIC_KAT_TRACK_PROFILE_LABELS_FOR_EXACT_FROZEN_COMPONENT_ONLY`

That state is component-local and cannot be promoted to evidence acceptance,
runtime admission, output authorization, or a production mitigation.

## Frozen managed and self-hosted profiles

Managed profile:

```text
track_id                        = MANAGED_SPANNER_CLOUD_KMS
t06_receipt_content_sha256      = c06e2502c405fa7e46d1cf138a405fb6db4d2228c7070a3a934d7f0b69fff655
packet_profile_id               = KAT_MANAGED_SYNTHETIC_EVIDENCE_PACKET_PROFILE_V1
provider_or_lab_profile_id      = KAT_MANAGED_SPANNER_CLOUD_KMS_PROVIDER_OR_LAB_PROFILE_V1
namespace_id                    = KAT_MANAGED_TRACK_PROFILE_BINDING_NAMESPACE_V1
configuration_sha256            = ad4d8cc3bd1342d79eea7fcef83247a76bfef1343fb3e8bcdca9db75d2eeae0c
```

Self-hosted profile:

```text
track_id                        = SELF_HOSTED_ETCD_OPENBAO
t06_receipt_content_sha256      = cbd73137fb31258c445d2244839aa027738770f1bebf374445fae8e05ed11ad3
packet_profile_id               = KAT_SELF_HOSTED_SYNTHETIC_EVIDENCE_PACKET_PROFILE_V1
provider_or_lab_profile_id      = KAT_SELF_HOSTED_ETCD_OPENBAO_PROVIDER_OR_LAB_PROFILE_V1
namespace_id                    = KAT_SELF_HOSTED_TRACK_PROFILE_BINDING_NAMESPACE_V1
configuration_sha256            = 192b74a49444883fe694c2e756ee35bdfdeb73c18097d3493e60eaba45c27dc7
```

The configuration hashes are fixed public KAT values. All labels are
non-secret. Their names do not authenticate a provider, lab, namespace,
tenant, packet profile, configuration, owner, subject, or external current
state.

## Resource binding

Allowed implementation resources are existing local CPU and memory, one
isolated Agent-Bridge worktree, committed non-secret public-only fixtures, and
private local test scratch. The reference component is limited to the Python
standard library and may not fetch dependencies.

The frozen component limits are:

- one worker and one T06 predecessor review call per successful review;
- 67,108,864 bytes of private scratch at each checkpoint;
- frame: 1,048,576 bytes;
- detached authentication bundle: 65,536 bytes;
- separately injected trust policy: 65,536 bytes;
- separately injected signer authorization policy: 65,536 bytes;
- detached authorization request: 16,384 bytes;
- separately injected track/profile binding policy: 65,536 bytes;
- detached track/profile binding request: 16,384 bytes;
- JSON depth 32, nodes 4,096, object members 256, and array items 64;
- exactly two track/profile binding entries; and
- each profile string at most 256 UTF-8 bytes, while frozen profile values are
  exact, trimmed, ASCII, non-empty, and wildcard-free.

Runtime network, provider endpoints, credential handles and paths, ambient or
system trust, real evidence input, private keys, seed material, signing, key
generation, custody, replay ledger, and trusted production time are forbidden
or bound to `NONE`. Effective external paid spend is zero in every currency.
Zero is a fail-closed default under reversible autonomy, not an owner-supplied
budget reservation.

## Authority lifecycle

The closed-world states are:

```text
UNRECORDED_NO_AUTHORITY
  -> AUTHORIZED_T07_TRACK_PROFILE_BINDING_ISOLATED_LAB_EXACT_UNIT

UNRECORDED_NO_AUTHORITY
  -> REJECTED_FAIL_CLOSED

AUTHORIZED_T07_TRACK_PROFILE_BINDING_ISOLATED_LAB_EXACT_UNIT
  -> CONSUMED_SCOPE_COMPLETE

AUTHORIZED_T07_TRACK_PROFILE_BINDING_ISOLATED_LAB_EXACT_UNIT
  -> INVALIDATED_REQUIRES_NEW_DECISION
```

A source or fast replay reports no effective authority. An integrated full
decision replay may activate the exact authority but does not consume it. The
transition to `CONSUMED_SCOPE_COMPLETE` occurs only when the exact authorized
T07 successor is integrated and its own full gate passes.

Owner revocation or drift in baseline, successor identity, four request fields,
six policy dimensions, either profile, T06 receipt binding, policy separation,
input order, allowed operations, resource caps, reviewer topology, network,
credentials, endpoints, or side effects invalidates the authority and requires
a new decision. Global single use is not claimed to be proved by an external
ledger.

## Truth boundary and accounting

The decision proves an authority record over fixed synthetic labels. It does
not prove packet-profile truth, provider/lab-profile identity or currentness,
namespace identity or truth, configuration truth or currentness, a production
track, or production subject binding. T08 end-to-end subject binding and T09
content identity, quarantine custody, or replay CAS remain unimplemented.

Production accounting remains:

- production ingestion controls implemented/runtime-exercised: `0 / 14`;
- production threat specifications runtime-exercised: `0 / 20`;
- runtime prerequisites satisfied: `0 / 16`;
- real, validated, or accepted evidence items: `0`;
- downstream gates authorized: `0 / 4`;
- runtime owner identity, decision, readiness, and admission: false;
- runtime/provider authority: false; and
- runtime side effects unlocked: `NONE`.

The decision adds zero candidate components and exercises zero new threat
specifications. Its released T06 predecessor has four isolated-lab components
and locally covers T01-T06. The authorized future successor can bring the local
total to five components and T01-T07 only after that successor is implemented
and passes its own source, review, integration, and full replay gates.

## Reviewer and validation topology

The decision source is a pure in-memory closed-world reviewer. It performs no
filesystem, environment, clock, process, network, provider, credential,
randomness, signing, key-generation, or mutable-global-state I/O. It emits a
domain-separated, content-derived scalar receipt with 79 exact TSV fields.

The independent checker must reconstruct the expected record and receipt
without trusting source helpers, load JSON duplicate-safely with finite bounds,
rederive all section hashes, verify exact predecessor bytes and the T07
semantic split, mutate closed-world leaves and hashes, reject T08 leakage and
overclaims, and inspect source AST purity. Normal output must be stable across
frozen hash seeds; self-test output and counts are separately frozen.

The future implementation requires at least two independent read-only reviewer
lanes after its bytes are frozen:

1. `CONTRACT_CONFORMANCE_REVIEW`; and
2. `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`.

Lane identities must be distinct. No production security reviewer is bound,
and neither lane constitutes production security approval or owner handoff.

## Git and integration topology

The logical baseline is the exact released T06 integration
`1f44c69d31ae29d0cd6c90e84294b3ad0407d9a0`, tree
`718d53c74855f880b01c272276320ff890455356`, with parents
`632918db75f65030d3ac15bc991b51a9c938cba6` then
`0c1f56ef7e7db854d28ab020dffc55d4f6dc0300`.

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

The gate protects the seven decision paths and the nine direct dependency
paths. It invokes the exact released T06 gate once and serially: fast maps to
fast, and full-replay maps to full-replay. It does not invoke T05 or any deeper
predecessor separately because the T06 gate owns that closure. The frozen T06
fast receipt is 144 lines with SHA-256
`7af602062c704a0ef320b19033e1b28da1198cfdb0483ea2a7cf779e9e6fba6b`;
the T06 full-replay receipt is 145 lines with SHA-256
`aa3cac8c1c3d885f6a08064de0cab2153e5061d45fb16c98e1119db32f688652`.
Its pack receipt content identity is
`d752afaec8f79c6b762c6f00448c5ef858b52cffef54f695d382455a52b00c88`.

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

- Reviewer source: `fbd7fe686d38cad7db0e16622d969257257e92047907a7b50ca550996d262101`
- Independent checker: `243649c047facf5a577af1baec5c989c312d90a63af18ad47023819961925225`
- Owner decision record: `064b9215a94ab3f649898ef924e755354578ec5c51c0dc50b978a84fa914a6ce`
- Frozen expected TSV: `a95f4ee21ffdfb3d6bb55dd076ea2bd61121e94a70b938bedfaaa93d829c06fe`
- Pack manifest: `6d983ba964e28899f9f339427fe79c92f6d6f50ba9c4dca1f4e2f049d24b2c45`

Frozen direct dependency bindings:

- T06 schema: `8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca`
- T06 reviewer: `438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0`
- T06 checker: `cd845c7c4d565e816a0667ab2e4c70f8a19a563e612a564b83a0a357834c55a9`
- T06 synthetic fixture: `cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9`
- T06 expected TSV: `0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae`
- T06 manifest: `f189dd457e7070b918eee8d44d2e94ce28ddf78f2d03e8b32b4226b3b59415e3`
- T06 report: `b45f4c90c8fad48e02ca1567303705b3c41bf37a8d78e3f8eb18c49c7e3c3029`
- T06 gate: `db3ce063668144dc91fbb52ed4bebeb8c4937630789aaa6c3a69400332233444`
- Upstream T07 semantic fixture: `3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`

## Nonclaims

The machine-readable record explicitly denies production track/subject
binding, provider/profile currentness, namespace/configuration truth, owner or
subject identity, prerequisite/build/session/channel/schedule/row-set binding,
action/resource capability, evidence acceptance, output, runtime admission,
runner launch, fault injection, deployment, provider access, credentials,
trusted time, custody, replay protection, scientific/application claims,
production security approval, and derived Git publication authority.

It also denies that this decision itself implements T07, T08, or T09; that the
future local T07 KAT would be a production mitigation; that global single use
is proved; or that zero spend is a reserved owner budget.
