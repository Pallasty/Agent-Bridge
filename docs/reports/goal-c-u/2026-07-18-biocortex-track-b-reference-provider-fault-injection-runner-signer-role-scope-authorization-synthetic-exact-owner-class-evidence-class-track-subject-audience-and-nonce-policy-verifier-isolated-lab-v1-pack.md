# BioCortex Track B reference-provider fault-injection runner signer role/scope authorization synthetic verifier isolated-lab v1 pack

Date: 2026-07-18

Status: `FROZEN_IMPLEMENTATION_CANDIDATE_PENDING_EXACT_SOURCE_FAST_AND_ORDINARY_INTEGRATION_FULL_GATE`

## Outcome first

This pack implements one reversible, public-only, isolated-lab T06 candidate
component.  It composes exactly once with the frozen T05 bootstrap-trust
authentication reviewer and authorizes only one of two exact synthetic KAT
signers for one exact six-dimension request.  The policy is separately injected,
contains exactly two ordered `ALLOW` grants, and defaults to `DENY`.

The component is not production signer authorization.  It does not authenticate
an owner, provider track, subject, audience, or nonce; it does not prove nonce
freshness, single use, replay protection, content identity, or quarantine
custody; and it grants no evidence, output, runner, fault, provider, runtime,
deployment, credential, signing, network, or paid-resource authority.

## Frozen authority and source baseline

The exact implementation authority is the owner/resource decision integrated at:

- commit `9edc70a870023ebc8e081f61100577345d3c2850`;
- tree `261d8d60677229614b18f2eb10f2530648f70505`;
- parents, in order: `400550236a643867086464e681be1fd5d12e579f`,
  `4a298c5f5a8dce6c7482b46fc6b416246fb55547`.

Its integrated full receipt is 158 lines with SHA-256
`f7ebac3d39eeba74d4c8d1cd908c195b8f95340e20e4ca0a126605384d0f01ee`.
That replay verified T05 authority consumption and activated, but did not
consume, the single-use non-transitive authority for this exact successor:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_CLASS_TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The immutable source commit for this pack must have the decision integration as
its sole parent and must add exactly the eight paths listed in the manifest.
Any scope, policy, baseline, budget, network, credential, endpoint, reviewer
topology, or owned-path drift fails closed and requires a new decision.

## Exact six-input public API

```python
review_signer_role_scope_authorization(
    frame,
    detached_authentication_bundle,
    separately_injected_synthetic_trust_policy,
    separately_injected_synthetic_signer_authorization_policy,
    detached_authorization_request,
    mode,
)
```

The observable order is frozen:

1. `MODE_PREOBSERVATION_GUARD`
2. `T05_BOOTSTRAP_TRUST_AUTHENTICATION_REVIEW`
3. `SEPARATE_SIGNER_AUTHORIZATION_POLICY_REVIEW`
4. `DETACHED_AUTHORIZATION_REQUEST_REVIEW`
5. `EXACT_SINGLE_GRANT_MATCH_AND_T05_RECEIPT_BINDING`
6. `RECEIPT_BUILD`

`PRODUCTION`, unknown values, non-string values, and string subclasses reject
before any of the other five inputs is observed.  A synthetic review invokes
the exact frozen T05 public API once.  The policy is observed only after T05
succeeds, and the detached request is observed only after the complete policy
passes.  Caller-supplied predecessor receipts are not part of the API.

## Closed-world authorization policy

The policy has exactly seven top-level fields, exactly two ordered grants, no
explicit `DENY` grants, and these immutable controls:

| Control | Value |
|---|---|
| default effect | `DENY` |
| matching | `EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL` |
| zero matches | deny |
| multiple matches | deny |
| wildcard/prefix/hierarchy | forbidden |
| role/group/parent inheritance | forbidden |
| action/resource capability | absent and forbidden |

The request carries schema/version plus exactly these six scope dimensions:

1. `owner_class`
2. `evidence_class`
3. `track_id`
4. `subject`
5. `audience`
6. `nonce_scope`

Each scope value is non-empty ASCII, at most 256 bytes, and compared as exact
ASCII bytes.  Signer key ID, key version, role, declared role class, and T05
receipt hash are forbidden request fields.

### Ordered KAT profiles

| Field | Managed | Self-hosted |
|---|---|---|
| `track_id` | `MANAGED_SPANNER_CLOUD_KMS` | `SELF_HOSTED_ETCD_OPENBAO` |
| `grant_id` | `KAT_MANAGED_SIGNER_ROLE_SCOPE_GRANT_V1` | `KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_GRANT_V1` |
| signer key | `KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2` | `KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2` |
| signer version | `KAT_MANAGED_LEAF_KEY_VERSION_2` | `KAT_SELF_HOSTED_LEAF_KEY_VERSION_2` |
| signer role | `KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER` | `KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER` |
| subject | `KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1` | `KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1` |
| nonce | `KAT_MANAGED_SIGNER_ROLE_SCOPE_NONCE_V1_0001` | `KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_NONCE_V1_0001` |
| T05 receipt | `46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803` | `72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1` |

Both profiles use owner class
`SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1`, evidence class
`SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT`, declared role class
`SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY`, trust-policy SHA-256
`882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0`,
and the exact track-specific policy revision, frame hash, revocation snapshot,
audience, and vector-set bindings frozen in the authority decision.

## T05 receipt is the sole signer-identity source

The selected grant is an allow-set constraint, not an identity source.  The
successful receipt derives the actual signer tuple only from the T05 receipt:

| T05 receipt field | T06 constraint/output |
|---|---|
| `active_leaf_key_id` | `signer_key_id` |
| `active_leaf_key_version` | `signer_key_version` |
| `mapped_policy_leaf_role` and `track_leaf_role` | `signer_role` |
| `declared_role` | `declared_role_class` |
| `content_sha256` | `predecessor_receipt_content_sha256` |
| `track_id` | matching profile and request track label |
| `frame_sha256` | matching profile frame binding |
| `trust_policy_sha256` | matching profile trust-policy binding |
| `revocation_snapshot_revision` | matching profile snapshot binding |
| `vector_set_id` | matching profile vector binding |

The implementation additionally freezes the exact T05 receipt schema/version,
component state, synthetic execution mode, one signature verification, local
T05 true/T06 false state, declared-role authentication true, declared role not
being authorization, frozen snapshot not being currentness, three predecessor
components, and all runtime/provider/production fences.

## Strict JSON and resource envelope

Policy and request bytes require compact sorted-key UTF-8 canonical JSON with
no duplicate keys, floats, non-finite values, signed-int64 overflow, trailing
bytes, BOM, invalid UTF-8, noncanonical escapes, or unsupported value types.

| Limit | Bound |
|---|---:|
| input frame | 1,048,576 bytes |
| detached authentication bundle | 65,536 bytes |
| separately injected trust policy | 65,536 bytes |
| signer authorization policy | 65,536 bytes |
| detached authorization request | 16,384 bytes |
| grants | 2 |
| JSON depth | 32 |
| JSON nodes | 4,096 |
| object members | 256 |
| array items | 64 |
| scope string | 256 UTF-8 bytes; ASCII required |
| predecessor calls per success | 1 |
| parallel workers | 1 |
| private scratch checkpoint | 67,108,864 bytes |
| external paid spend | 0 |

The component uses only Python standard-library primitives plus the frozen T05
module.  It performs no fetch and exposes no filesystem, environment, clock,
randomness, process, network, credential, provider, private-key, signing,
mutable-cache, async, generator, persistence, or background-worker surface.

## Successful component receipt

The only successful component state is:

`AUTHORIZED_SYNTHETIC_KAT_SIGNER_FOR_EXACT_FROZEN_ROLE_SCOPE_COMPONENT_ONLY`

The receipt records one exact grant match; the six scope labels; the T05-derived
signer tuple and receipt bindings; raw policy/request hashes; T05 call count
one; four local candidate components; local T01–T06 coverage; and a
domain-separated content hash.

It explicitly keeps all of the following false or zero:

- production signer role/scope authorization and all 14 production controls;
- all 20 production threats runtime-exercised;
- all 16 runtime prerequisites satisfied;
- real, validated, or accepted evidence;
- provider/runtime/output/fault/deployment/runner authority;
- owner/audience/subject/track truth;
- nonce generation, freshness, single use, and replay protection;
- T07 track/profile binding and T08 end-to-end subject binding;
- T09 content-identity and quarantine-custody binding;
- action/resource capabilities and side effects.

The upstream decision's legacy `t09_replay_cas_implemented=false` field is
preserved only as an explicitly named upstream-record nonclaim; this pack does
not redefine T09 as durable replay CAS.

## Independent deterministic verification

The checker independently reconstructs the policy, requests, T05 inputs, T05
receipt constraints, and T06 receipts without using the subject's policy,
request, canonicalization, validation, or receipt helpers.  It checks positive
managed and self-hosted cases, mode pre-observation bombs, a one-call T05 spy,
policy-before-request ordering, signer-identity mutation rejection, JSON/resource
bounds, closed-world profile mutations, AST call/order/purity, and exact
fixture/schema bindings.

The independent checker passes under hash seeds 0, 1, and 42 with byte-identical
output:

| Receipt | Lines | SHA-256 |
|---|---:|---|
| normal TSV | 47 | bound exactly once in Artifact binding below |
| self-test | 16 | `51309f5ed95d1821253b8b36a65542b4446cf75cd1e15807a5111d4d2830aa36` |

The 241 directed negatives are: policy JSON 19, request JSON 18, policy
closed-world 66, request scope 85, receipt identity 38, default-DENY 7, mode
pre-observation 4, and T05 exactly-once/order 4.  There are also 17 source AST
guards and 19 fixture/schema guards.  Both positive profiles execute the real
T05 reviewer exactly once.

## Artifact binding

Frozen public artifacts before report/gate binding are:

| Artifact | Raw SHA-256 |
|---|---|
| schema | `8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca` |
| source | `438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0` |
| checker | `cd845c7c4d565e816a0667ab2e4c70f8a19a563e612a564b83a0a357834c55a9` |
| synthetic fixture | `cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9` |
| expected TSV | `0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae` |
| manifest | `f189dd457e7070b918eee8d44d2e94ce28ddf78f2d03e8b32b4226b3b59415e3` |

Managed and self-hosted component receipt content hashes are respectively
`c06e2502c405fa7e46d1cf138a405fb6db4d2228c7070a3a934d7f0b69fff655`
and `cbd73137fb31258c445d2244839aa027738770f1bebf374445fae8e05ed11ad3`.
The frozen authorization policy SHA-256 is
`7d7fcc3174560c0d121aff8ce69e02c5facbcbe799f0ad2f523ecc108f6cb1c9`.

The two required immutable-source reviewer lanes are:

1. `CONTRACT_CONFORMANCE_REVIEW`
2. `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`

These are semantic reviewer identities only; this pack does not claim
cryptographic owner or reviewer identity binding.

## Source-bound gate and authority consumption

The gate accepts only:

- an exact source commit whose sole parent is `9edc70a8...`; or
- an ordinary two-parent integration whose second parent is that exact source
  shape and whose first parent descends from the baseline without already
  containing the source.

The source and integration first-parent deltas must both be the exact eight-path
all-add packet.  Protected predecessor/authority artifacts are frozen by raw
hash, mode, index/blob identity, and a source-commit archive.  The direct static
closure is T05 owned 8 + T05 frozen direct dependencies 23 + current T06
authority decision 7 + T06 semantic specification 1 = 39 dependencies; with
the owned packet, the protected archive contains exactly 47 unique paths.  The
checker is replayed in clean isolated environments with multiple hash seeds.

The gate invokes the frozen T06 authority-decision gate exactly once and
serially.  Fast calls fast; integrated full calls full.  It does not separately
or concurrently invoke T05 because the authority gate owns that deeper chain.

- source fast: non-release; authority remains inactive and unconsumed;
- integrated fast: non-release; authority remains inactive and unconsumed;
- failed full: does not consume authority;
- exact ordinary integration plus passing full: verifies active authority and
  transitions this exact implementation to `CONSUMED_SCOPE_COMPLETE`.

Decision replay, Git revert, or copying artifacts cannot restore the consumed
authority or authorize another successor.  Global single use remains unproved
because there is no external ledger.

Recursive gates must run as exactly one managed process chain.  Source fast,
integrated fast, and integrated full are executed serially while polling the
same process/session; concurrent delegated replays are forbidden because they
can exhaust memory and swap.

## Rollback and next boundary

Before publication, delete the isolated worktree.  After publication, use a
normal Git revert of the exact eight-path packet.  No production kill switch is
needed because no production or runtime surface is enabled.  Revert does not
restore single-use authority.

This pack does not authorize T07, T08, T09, provider execution, evidence
ingestion, a runner launch, or fault injection.  Any successor requires a new
owner/resource decision after this exact implementation's integrated full gate
passes and its authority consumption is recorded.
