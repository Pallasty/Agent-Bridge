# Track B bootstrap-trust authentication synthetic verifier isolated-lab v1 pack

Date: 2026-07-17
Status: `FROZEN_IMPLEMENTATION_PENDING_EXACT_SOURCE_FAST_AND_ORDINARY_INTEGRATION_FULL_GATE`
Decision: `IMPLEMENT_EXACT_BOUNDED_PUBLIC_ONLY_SYNTHETIC_BOOTSTRAP_TRUST_AUTHENTICATION_VERIFIER_FAIL_CLOSED`

## Outcome

This pack adds one reversible, isolated-lab candidate component for the exact
authorized successor:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`

The component accepts only committed nonsecret synthetic KAT material.  It
composes with the frozen predecessor frame reviewer, validates one separately
injected closed-world two-track synthetic trust policy and one detached
authentication bundle, constructs the exact raw-frame message, and performs
one strict active-leaf Ed25519 verification for the selected track.

The only positive component state is:

`AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY`

This is not production authentication, role/scope authorization, track-subject
authorization, provider compatibility evidence, current revocation evidence,
trusted time, evidence acceptance, runtime admission, or security approval.

## Exact source baseline and topology

The immutable source baseline is
`61585e655f7bfd537f8a123141e4e39a590a66d8`, tree
`9dcd1f700a7e4523307ef9704218b9f87a7fe5f1`, with parents in order:

1. `2a0028eacc8fdd36463d4fa2f297f4d19807cd65`
2. `4ce033e70781a5886d986939e879f6e3f7eadebd`

The source commit must have that baseline as its exact sole parent and add
exactly eight paths.  A release candidate must be an ordinary two-parent merge
whose second parent is that immutable source commit and whose first parent is
the baseline or a descendant that does not already contain the source.  The
integration first-parent delta must remain the same exact eight additions.

Source and integration commit identifiers are intentionally not embedded in
their own source bytes.  The gate derives and emits them from Git topology,
avoiding a self-referential hash cycle.  Squash, rebase-shaped, fast-forward,
octopus, dirty-index, dependency-byte, path-mode, or first-parent-delta drift
fails closed.

## Four disjoint inputs and pre-observation mode boundary

The public entrypoint is
`review_bootstrap_trust_authentication(frame, detached_authentication_bundle, separately_injected_synthetic_trust_policy, mode)`.
It has exactly four inputs and no ambient source of trust.

`PRODUCTION`, an unknown string, and a non-string mode reject before the
function reads, sizes, hashes, parses, compares, or otherwise observes the
other three inputs.  Only `SYNTHETIC_KAT` enters the component path.  The
checker uses observation bombs to exercise that ordering directly.

On the synthetic path:

1. the exact frame is passed to the frozen predecessor `review_frame` API in
   `SYNTHETIC_KAT` mode;
2. trust-policy and detached-bundle JSON are duplicate-safe, bounded and
   canonicalized independently;
3. root, issuer, leaf, exact key versions, role map, policy revision,
   revocation snapshot and signature domain are selected from the separately
   injected frozen policy;
4. bundle fields are treated as untrusted references and must agree exactly
   with the selected policy profile;
5. the detached message is constructed from the exact original frame bytes;
   and
6. the selected active leaf performs exactly one signature equation.

The frame and bundle cannot inject a root, substitute a track, select
`LATEST`/zero/unknown versions, override the policy, or establish trust on
first use.  A cross-track consistency guard is synthetic profile
non-substitution only; it does not implement T06 or T07.

## Frozen track profiles

The two non-substitutable tracks are:

- `MANAGED_SPANNER_CLOUD_KMS`
- `SELF_HOSTED_ETCD_OPENBAO`

Each policy chain has exactly three structural entries: root v1, policy issuer
v1, and evidence-envelope signer v2.  Leaf v1 is frozen as revoked negative
material.  The two tracks have distinct public keys, identifiers, versions,
roles, policy revisions, revocation snapshots, vector-set identifiers and
signature domains.

The generic role class
`SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY` maps to the exact track-specific
leaf role.  That mapping is a checked label, not authorization for an owner,
evidence class, track, subject, audience, nonce, output, application, or any
other scope.

## Cryptographic boundary

The algorithm is verification-only pure RFC 8032 Ed25519 without context or
prehash.  Public keys are exactly 32 bytes and signatures exactly 64 bytes.
The verifier rejects noncanonical/off-curve points, identity and torsion/small
order points, points outside the prime-order subgroup, malformed encodings,
wrong lengths, and `S >= L`.

For each accepted track the message is constructed without parsing or
reserializing the frame:

```text
u64be(len(signature_domain)) || signature_domain ||
u64be(len(exact_canonical_raw_frame)) || exact_canonical_raw_frame
```

All six policy public keys receive strict point validation.  Signature `R`
receives the same strict point treatment.  Only the selected active leaf is
used in a signature equation; root and issuer entries are structural frozen
policy inputs, not certificate-link signatures.

No signing, key generation, private seed, certificate creation, remote key
retrieval, system trust store, CRL/OCSP, provider endpoint, credential or
production trust root exists in the component.

## Bounds and purity

The implementation is a pure in-memory Python standard-library reference KAT
component.  It has no filesystem, environment, clock, process, socket,
provider, credential, random, entropy, mutable cache or persistence input.

Frozen limits are:

- exact predecessor frame cap: 1,048,576 bytes;
- detached authentication bundle: 65,536 bytes;
- separately injected trust policy: 65,536 bytes;
- JSON depth 32, nodes 4,096, object members 256 and array items 64;
- exactly two trust roots and two tracks in the frozen policy;
- exactly three chain entries per track;
- exactly six distinct public keys;
- exactly one active-leaf signature verification per accepted review;
- one worker; and
- 67,108,864 bytes at each private gate-scratch checkpoint.

The source gate runs from a protected archive in an empty environment with
`python3 -B -S -P` under three hash seeds.  It requires byte-identical stdout,
empty stderr, and no Python cache.

## Independent checker and adversarial oracle

The checker independently reconstructs the closed field sets, track profiles,
policy/bundle separation, raw-frame message, SHA-256/SHA-512 anchors,
revocation oracle and strict Ed25519 equation.  It does not call the
implementation's private JSON, message, point or verification helpers.

The frozen runtime rejection/probe total is
`116`.  Its mutation families include:

- production/unknown/non-string mode observation bombs for every non-mode
  input;
- predecessor-before-policy and policy-before-bundle observation ordering;
- duplicate keys, noncanonical JSON, encoding/BOM/whitespace, nonfinite and
  floating-point numbers, int64, depth, node, member, item and byte bounds;
- frame hash/length and parse-reserialize drift;
- track/vector/domain/algorithm/scheme/message-profile substitution;
- chain order/count and root/issuer/leaf ID, key-version and role drift;
- `LATEST`, zero, missing, revoked, unknown and fail-open state mutations;
- role-map, policy-revision and revocation-snapshot substitution;
- public-key length/hex/case/duplication, identity, small-order,
  noncanonical, off-curve and non-prime-subgroup mutations;
- signature length/hex, R, `S >= L`, bit flip and cross-track mutations.

Separately from those 116 runtime probes, 15 static source guards bind the
four-argument API, first mode guard, sole predecessor call site and ordering,
sole active-leaf verification call site, reuse of the already validated leaf
point, allowed imports, and no I/O/process/network/clock/random/signing/keygen/
mutable-cache/async surface.  Another 23 fixture/schema guards bind the two
positive frames, bundles, complete receipts and closed schema.  Positive
receipts expose an exact verification count of one.  The checker does not
claim runtime spy/counter instrumentation for structurally rejected cases.
The source-bound gate separately freezes the exact expected-TSV and manifest
bytes.

The checker normal stdout is `44` lines and is
byte-identical to the expected TSV whose digest is bound below.  Its self-test stdout is
`13` lines with SHA-256
`921bf2a83c28348a95905f6b4c41349372d38a9489a1ce3b96baa42116a4bf8c`.

## Direct dependency and replay topology

The gate freezes exactly 23 direct dependency artifacts:

- all eight public-vector supply pack artifacts;
- all seven original bootstrap-trust implementation-authority pack artifacts;
  and
- all eight predecessor frame/mode implementation pack artifacts.

Together with the eight owned paths, the source archive therefore protects
exactly 31 paths.  The fixture-custodian amendment is not duplicated as a
direct dependency because the supply gate already owns and replays that
chain.

The exact supply predecessor is the ordinary integration
`61585e655f7bfd537f8a123141e4e39a590a66d8`.  Its gate raw SHA-256 is
`ecc81672ea4754a85128b084e6f4f5d17d3f9e3982cb9224333994138b2f8972`.

- integrated supply fast receipt: 50 lines,
  `dcd18e07ca5e25dfbb33a6903a65883efd534f35772b0676d9e74e33d91bae67`
- integrated supply full receipt: 51 lines,
  `7c48aa07f3a4fc0aa06b57d8f8bf7a00f1e03ad3dce5b96828498d911f6f3e37`

The successor gate invokes only that supply gate at the matching validation
tier.  The supply full gate owns the single recursive chain through the
fixture-custodian amendment, original implementation authority, frame/mode
implementation and older frozen predecessors.  The successor does not invoke
the authority full gate a second time.

## Git and protected-archive boundary

The gate rejects shallow history, replace refs, grafts, alternates, common
info attributes, working-tree attributes, executable filters/diff/merge
drivers, includes, symlink path components, hardlinked protected files,
nondefault index flags, mode drift and dirty state.  It binds baseline,
source, HEAD and index blob identity for all owned paths, and immutable
baseline/source/HEAD identity for all 23 dependencies.

An isolated `--no-local --no-hardlinks --no-tags --single-branch` sparse clone
checks out the exact supply integration.  The supply gate's executable mode,
regular-file identity, hardlink count and raw hash are verified before direct
execution.  HEAD and cleanliness are checked again after nested replay.

## Authority consumption and release semantics

The fixture-generation authority is already consumed and cannot be restored
or retried by this pack.  The implementation authority remains effective and
unconsumed at the source baseline.

Source existence, source fast, integrated fast, and a failed full replay do
not consume the implementation authority.  Only a successful full replay of
the exact ordinary integration reports:

```text
authorization_consumption_state = CONSUMED_SCOPE_COMPLETE
implementation_authority_single_use_consumed = true
artifact_release_evidence = true
```

After that event, a replay verifies the same release; it does not authorize a
second successor.  A Git revert does not restore authority.  The authority is
not backed by an external global ledger, so `global_single_use_proved` remains
false.

At integrated full passage, local candidate components become 3 and local
threat specifications become T01-T05.  Production ingestion controls remain
`0 / 14`, production threat cases runtime-exercised remain `0 / 20`, runtime
prerequisites remain `0 / 16`, real/validated/accepted evidence remains 0,
and runtime/provider authority remains false.

## Reviewer topology

After source bytes are frozen and before ordinary integration, two independent
read-only lanes are required:

1. `CONTRACT_CONFORMANCE_REVIEW`
2. `SECURITY_AND_SOURCE_BOUND_GATE_REVIEW`

Their semantic reviewer identities must differ from each other and from the
implementation lane.  The deterministic checker is not either review and is
not a production security approval.  Reviewer outcomes should bind the exact
source tree externally; inserting a post-review receipt back into this pack
would change the reviewed bytes.

## Rollback

Before integration, rollback is deletion of the isolated branch/worktree.
After integration, rollback is an ordinary revert of the exact integration.
There is no runtime process, deployment, endpoint, credential, secret,
provider call, external spend, experiment row, accepted evidence or durable
state to unwind.

## Nonclaims

- No production authentication, mitigation, security approval or provider
  cryptographic compatibility claim.
- No role/scope, track-subject, audience, nonce, output or application
  authorization.
- No assertion that the frozen revocation snapshot is current or fresh.
- No certificate-path validation or root/issuer link-signature claim.
- No real evidence collection, authentication, ingestion, acceptance,
  quarantine, custody, replay ledger or experiment row.
- No runner launch, fault injection, deployment, production registration,
  runtime admission or downstream-gate authority.
- No memory, retrieval, storage-efficiency, application, scientific, product
  or biological-brain conclusion.

## Artifact binding

- Schema: `d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c`
- Pure verifier source: `f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341`
- Independent checker: `bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20`
- Synthetic KAT fixture: `31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e`
- Expected TSV: `0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36`
- Pack manifest: `bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b`

The report and gate deliberately do not embed their own raw hashes.  The gate
binds this report, all other owned artifacts and all 23 dependencies; the Git
source/integration topology and a future successor bind the gate itself.
