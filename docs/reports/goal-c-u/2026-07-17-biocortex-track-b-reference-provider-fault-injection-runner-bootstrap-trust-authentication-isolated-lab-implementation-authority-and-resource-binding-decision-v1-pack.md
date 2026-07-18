# Track B bootstrap trust/authentication isolated-lab implementation authority and resource-binding decision v1

Date: 2026-07-17

## Outcome

`REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY`

The owner-facing direction to continue the next bounded unit records one exact,
reversible, local repository implementation decision:

`AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED`

The record names a public-only synthetic bootstrap-trust authentication
candidate. It does not authorize production trust, a real signer, private-key
or seed material, signing, provider access, runtime registration, evidence
ingestion, a runner, a fault, deployment, or any downstream output or claim.

The decision record is inert on a source or fast replay. Only an ordinary
two-parent integration followed by the serialized full gate makes the new
single-use implementation authorization effective. That activation does not
consume the new scope; only the exact authorized successor's later integrated
full gate may consume it.

## Three authority planes remain separate

| Plane | State after integrated full gate | Meaning |
|---|---|---|
| Planning direction | `ISOLATED_LAB_FIRST` | Continue the bounded offline sequence |
| Exact implementation unit | one single-use local authorization | Public-only synthetic verifier work for one named successor |
| Runtime / provider / production | not authorized | No root, key, endpoint, credential, evidence, execution, or activation authority |

The prior frame/mode authorization is already
`CONSUMED_SCOPE_COMPLETE`; it cannot be reused. The new authorization is
non-transitive, default-off, and limited to reversible code, schema, tests,
fixtures, documentation, checker, report, and source-bound gate work.

## Owner-label semantics

The semantic implementation actor is `pallasting`, role label
`PROJECT_OWNER`, grounded in the established project profile, the standing
reversible-work autonomy policy, and the current instruction to continue.
This is not cryptographic identity authentication:

- no owner signature or identity proof was observed;
- runtime owner identity and decision remain unbound;
- no credential, endpoint, key, or production trust root was accessed; and
- the semantic label cannot substitute for a signed production decision.

External paid spend is zero across all currencies. Zero is a fail-closed agent
default under reversible autonomy, not an owner-supplied budget reservation.

## Exact authorized successor

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The successor may implement one bounded candidate component: a closed-world,
public-only synthetic trust policy plus detached authentication bundle and a
pure offline verifier. The target production control is
`BOOTSTRAP_TRUST_AUTHENTICATION`; the only production-boundary threat
specification that may be locally modeled is `T05`.

Authorization does not mean implementation. This decision unit adds zero
candidate components and zero threat coverage. The predecessor remains at two
locally implemented/KAT-exercised frame/mode components and T01-T04 locally
covered. Even after the successor passes local KATs, production control
implementation and runtime exercise remain `0 / 14`; T05 remains a local
specification exercise, not a production mitigation.

`SIGNER_ROLE_SCOPE_AUTHORIZATION` and T06 are explicitly excluded. A declared
role authenticated as part of a synthetic chain is only a signed label. It
does not authorize that signer for an owner class, evidence class, track,
subject, audience, nonce, or any other scope.

## Separately injected trust policy

The future public API must receive four disjoint inputs:

1. the exact predecessor-reviewed frame;
2. a detached authentication bundle;
3. a separately injected synthetic trust policy; and
4. the explicit mode.

`PRODUCTION` and unknown modes must reject before observing any of the other
three inputs. The root public key or fingerprint, chain policy, exact key
versions, declared roles, and revocation snapshot may come only from the
separate trust-policy input. The untrusted frame and authentication bundle may
reference those identities but may not supply or override them. Trust on first
use, self-asserted `ACTIVE`, self-asserted role, policy/bundle aliasing, ambient
trust stores, and remote chain retrieval are forbidden.

The two synthetic tracks are non-substitutable:

- `MANAGED_SPANNER_CLOUD_KMS`; and
- `SELF_HOSTED_ETCD_OPENBAO`.

Each track must use a distinct synthetic root, issuer, leaf signer, key-version
identifiers, policy revision, revocation snapshot, role labels, and
domain-separated signature subjects. Each active chain is exactly three
entries: root v1, policy issuer v1, and evidence-envelope signer v2. A separate
leaf v1 is frozen as revoked negative material. Only public keys and
precomputed signatures may be committed; seeds and private keys are forbidden.

## Cryptographic KAT boundary

The allowed algorithm profile is verification-only, pure RFC 8032 Ed25519
without context or prehash. Public keys are exactly 32 bytes and signatures
exactly 64 bytes. The reference verifier must reject non-canonical points,
identity or small-order points, non-prime-subgroup inputs, `S >= L`, wrong
lengths, algorithm substitution, `Ed25519ctx`, and `Ed25519ph`.

The detached signature message is constructed without parsing and
reserializing the predecessor frame:

```text
u64be(len(domain)) || domain ||
u64be(len(exact_canonical_raw_frame)) || exact_canonical_raw_frame
```

The signature domains are isolated-lab KAT domains and must never reuse the
future production signature domain. SHA-512 is used only as required by RFC
8032; SHA-256 lower hex remains the identity/content-digest representation.
The only positive component state is
`AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY`.

This is a conformance candidate, not proof of production cryptographic
fitness, provider compatibility, current revocation status, trusted time, or
security approval.

## Resource binding

Allowed resources are existing local CPU and memory, one isolated
Agent-Bridge worktree, committed non-secret public-only fixtures, and private
local scratch. No dependency addition, filesystem input, environment input,
clock, randomness, process spawn, socket, provider, system trust store, or
ambient credential source is allowed in the component.

The frozen limits are:

- one worker and at most 67,108,864 bytes at each private-scratch checkpoint;
- input frame 1,048,576 bytes;
- authentication bundle 65,536 bytes;
- synthetic trust policy 65,536 bytes;
- JSON depth 32, object members 256, array items 64, and nodes 4,096;
- exact chain depth 3, at most two roots, 64 revocation rows, and 16 role rows;
- no more than three signature verifications per review; and
- 32-byte public keys and 64-byte signatures only.

Provider endpoints, credential handles and paths, production trust roots,
production signers, actual key versions, provider resource IDs, trusted time,
CRL/OCSP, custody, replay, and production rollback bindings remain `NONE`.

## Reviewer topology

The successor must receive two independent read-only review lanes after its
bytes are frozen: a contract/claim-boundary review and a security/gate review.
Their semantic reviewer identities are recorded at successor review time and
must differ from the implementation lane. The independent checker must
reconstruct the canonical message, domains, key-version and revocation oracle
without calling the implementation's helpers.

Neither lane is a production security reviewer. The production security
reviewer and independent production-review identity remain unbound. Passing
the checker cannot satisfy `INDEPENDENT_REVIEW_BINDING`, control 11, or any
owner-handoff requirement.

## State and activation

The closed-world decision states are:

```text
UNRECORDED_NO_AUTHORITY
  -> AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT

AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT
  -> CONSUMED_SCOPE_COMPLETE

AUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT
  -> INVALIDATED_REQUIRES_NEW_DECISION

UNRECORDED_NO_AUTHORITY
  -> REJECTED_FAIL_CLOSED
```

The record names the authorized state, but a source/fast replay reports
`UNRECORDED_NO_AUTHORITY_PENDING_DECISION_INTEGRATED_FULL_GATE`. Only the
ordinary integration/full gate reports the effective authorized state. Owner
revocation or drift in the baseline, exact successor, algorithm, domains,
message construction, trust topology, key versions, roles, revocation
snapshot, allowed operations, resource caps, reviewer topology, network,
credentials, endpoints, or side-effect surface invalidates the authorization.

## Rollback

Before merge, rollback is deletion of the isolated worktree and branch. After
merge, rollback is an ordinary Git revert of the exact source/integration
change. Because committed material is public-only and the component has no
runtime, endpoint, credential, provider, or external state, no secret cleanup,
production kill switch, or runtime disable action applies. Any future
production rollback operator remains unbound.

## Verification and Git boundary

The pure reviewer accepts one exact closed-world decision record in memory and
emits a content-derived scalar receipt. It performs no file, environment,
clock, process, network, provider, credential, randomness, or mutable-state
I/O. The independent checker repeats the contract and hash derivation,
duplicate-safe finite JSON loading, predecessor binding, overclaim rejection,
and source AST purity checks.

The exact source baseline is
`d0356dbdbd7239ffab972ee21da81891210a055b`, tree
`b40c36c5fe73af3079bf3a81d69480d2555271d8`, with parents
`3bf8ad3a67ff02a4e717db8e29e89079f66c01cf` then
`20368c626bf34c5a1edd07391014ab8716536e7e`.

The semantic predecessor is the frame/mode integration
`3bf8ad3a67ff02a4e717db8e29e89079f66c01cf`, whose old implementation
authorization is consumed. Its exact eight artifacts and complete fast/full
receipts are frozen and replayed.

A source commit must have the baseline as its exact sole parent and add exactly
seven paths. Integration must be an ordinary two-parent merge whose second
parent is that immutable source commit and whose first parent descends from
the baseline without already containing the source. Fast replay is always
non-release. Full replay is integration-only and serialized. Squash,
rebase-shaped, fast-forward release, octopus, replace-ref, graft, file-mode,
alias, index-flag, hash-seed, or predecessor-byte substitutions fail closed.

The gate uses protected-artifact archives and one sparse predecessor checkout.
The 64 MiB value is a checkpoint cap on the successor gate's scratch tree, not
a filesystem quota or a global aggregate across nested predecessor gates.

## Claim and authority ceiling

After the integrated full gate:

- exact successor local implementation authorization: one, single-use;
- decision-unit candidate implementation: `0`;
- predecessor local candidate components: `2`;
- predecessor local threat specifications: `4 / 20` (`T01`-`T04`);
- target successor local threat specification: `T05` only;
- production-ingestion controls implemented/runtime-exercised: `0 / 14`;
- production threat cases runtime-exercised: `0 / 20`;
- real, validated, or accepted evidence items: `0`;
- runtime prerequisites satisfied: `0 / 16`;
- runtime owner identity/decision/admission: false;
- runtime/provider authority: false;
- downstream gates authorized: `0 / 4`; and
- runtime side effects unlocked: `NONE`.

The only positive authority is reversible local code/schema/test/docs work for
the exact successor. The production prerequisite
`TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND` remains unsatisfied because the
control is not satisfiable offline and no external root, key, provider,
revocation-currentness source, trusted time, or production reviewer is bound.

## Artifact binding

- Reviewer source: `f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c`
- Independent checker: `7c5f1dcd53db8bdf9360e8e00a6495daa40b97d21fbf4efa1f9f3392bfbd6136`
- Owner decision record: `05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b`
- Frozen expected TSV: `79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f`
- Pack manifest: `e521a7aab3a3fa00dacade4da1bf88834680a878d4de425f77918734655e255e`
- Predecessor schema: `e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55`
- Predecessor reviewer: `bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1`
- Predecessor checker: `76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf`
- Predecessor fixture: `324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9`
- Predecessor expected TSV: `775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847`
- Predecessor manifest: `9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04`
- Predecessor report: `a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149`
- Predecessor gate: `464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174`
- Predecessor receipt content: `4d5752110ebf0c11197bd8667fb9e79948724f5195465e41c6709d98d6177b8c`

## Nonclaims

The machine-readable record denies production authentication, trust-root,
signer, key-version, role-policy, revocation-currentness, endpoint, credential,
trusted-time, custody, replay, reviewer, owner, runtime, provider, downstream,
output, scientific, and application authority. It also denies private-key or
seed presence, signing or key generation, provider compatibility, production
fitness, security approval, T06 authorization, evidence acceptance, global
single-use proof, and derived Git publication authority.
