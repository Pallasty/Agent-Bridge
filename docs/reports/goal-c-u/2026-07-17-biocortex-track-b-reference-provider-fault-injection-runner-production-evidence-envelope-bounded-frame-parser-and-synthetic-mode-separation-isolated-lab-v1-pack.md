# Track B production-evidence envelope bounded-frame parser and mode separation v1

Date: 2026-07-17

## Outcome

`REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_ENVELOPE_BOUNDED_FRAME_AND_SYNTHETIC_MODE_SEPARATION_ISOLATED_LAB_COMPONENTS_IMPLEMENTED_LOCAL_KAT_CONFORMANT_PRODUCTION_CONTROLS_ZERO_RUNTIME_UNBOUND`

This pack implements the two exact component surfaces authorized by the
preceding `ISOLATED_LAB_FIRST` decision:

1. a bounded, duplicate-safe UTF-8 JSON frame parser; and
2. explicit synthetic/production execution-mode separation.

Both are reversible local code/schema/test artifacts. They are exercised only
against committed, non-secret synthetic KATs. They are not wired into a
runtime, provider, endpoint, evidence collector, quarantine store, replay
ledger, deployment, or production entry point.

The component decision is:

`ISOLATED_LAB_FRAME_AND_MODE_COMPONENTS_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED`

## Correct control accounting

The earlier production-ingestion boundary defines fourteen controls and marks
every one, including `FRAME_AND_PARSE` and
`SYNTHETIC_PRODUCTION_MODE_SEPARATION`, as
`satisfiable_by_offline=false`. Full `FRAME_AND_PARSE` also requires a bounded
quarantine contract, which remains absent.

Therefore this pack records:

- isolated-lab candidate component surfaces implemented: `2 / 2`;
- isolated-lab candidate component surfaces locally KAT-exercised: `2 / 2`;
- boundary threat specifications locally KAT-covered: `4 / 20` (`T01`–`T04`);
- production-ingestion controls implemented: `0 / 14`;
- production-ingestion controls runtime-exercised: `0 / 14`; and
- production threat cases runtime-exercised: `0 / 20`.

Local KAT coverage is not production mitigation, production validation, a
security approval, or evidence admission.

## Bounded frame contract

The parser accepts an exact `bytes` value and enforces these fail-closed
limits before returning a structure:

- input length `1..1,048,576` bytes;
- strict UTF-8 with UTF-8/16/32 BOM rejection;
- exactly one top-level JSON object with no leading, trailing, or concatenated
  bytes;
- recognized compression byte signatures and enumerated compression or
  URI/reference metadata shapes rejected;
- duplicate keys rejected before a decoded object is returned;
- all floating-point and non-finite tokens rejected;
- signed 64-bit integers only;
- JSON depth at most `32`;
- at most `256` members per object;
- at most `64` items per array; and
- a single worker with deterministic standard-library execution.

Rejecting all floats and bounding integers are deliberately stricter local
framing policies. They do not constitute prerequisite-specific semantic
validation.

## Closed-world envelope contract

The separate Draft 2020-12 schema defines two exact track-specific variants of
one production-shaped isolated-lab KAT envelope. Its schema/version, packet
kind, canonicalization profile, hash domain, fixture marker,
production-admissibility marker, track, prerequisite identity, and inline KAT
payload are closed-world. Compression and remote-reference fields are absent
from the schema, so every additional field fails closed during envelope
review; the frame parser separately rejects its enumerated metadata shapes and
recognized compression byte signatures.

The successful result is only
`PARSED_ISOLATED_LAB_KAT_COMPONENT_ONLY`. It can carry ephemeral raw,
canonical, and domain-separated hashes for deterministic comparison. It does
not create custody, retain bytes, authenticate a signer, validate evidence, or
produce a production evidence receipt.

Known synthetic packet kinds/domains, unknown or alternate production
domains, case drift, Unicode-confusable identities, missing/extra keys,
compression, remote references, and forbidden authority fields fail closed.
The production-shaped KAT domain is non-substitutable with
`AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1`.

## Execution-mode separation

Execution mode is an API parameter separate from envelope-declared identity.
Every supported public frame-ingress API requires that parameter. Only the
isolated synthetic KAT mode can reach frame parsing through those APIs.
`PRODUCTION` and unknown execution modes are rejected before the frame value
is inspected, preventing a supported public entry point from becoming a
production content oracle.

The lower parser API's successful synthetic-mode return is only an ephemeral
decoded structure; it is not an envelope-review receipt or evidence state.
There is no production-success state. The closed-world envelope-review
outcomes are:

```text
UNPARSED_LOCAL_KAT_ONLY
  +-> FRAME_REJECTED_FAIL_CLOSED
  +-> MODE_REJECTED_FAIL_CLOSED
  +-> ENVELOPE_REJECTED_FAIL_CLOSED
  `-> PARSED_ISOLATED_LAB_KAT_COMPONENT_ONLY
```

Even the positive local terminal state has no evidence-acceptance, runtime, or
authority semantics.

## Threat boundary

The synthetic suite covers the specifications associated with:

- `T01`: malformed/oversized, BOM, trailing/concatenated, compression, and
  remote-reference framing;
- `T02`: duplicate-key, numeric, alternate-encoding, depth, object-member,
  and array-item parser differentials;
- `T03`: synthetic packet/domain substitution at a production-shaped
  boundary; and
- `T04`: unknown or drifting schema/version/kind/domain/canonicalization.

`T05`–`T20` remain deferred and unimplemented. This component does not judge
authentication, signer authorization, track/subject binding, custody,
semantic validity, trusted time, replay, validation receipts, independent
review, owner handoff, owner identity/decision, or downstream gates.

## Authorization consumption

The predecessor authorized exactly this single successor and prohibited
transitive reuse. A source commit alone is non-release evidence. Only an
ordinary source-bound integration followed by the serialized full gate changes
the authorization state from
`AUTHORIZED_ISOLATED_LAB_FIRST_EXACT_UNIT` to `CONSUMED_SCOPE_COMPLETE`.

Revocation or drift in the actual baseline, exact successor identity, allowed
operations, resource classes/caps, network policy, credentials, endpoints, or
side-effect surface invalidates the scope and requires a new decision. This
pack grants no authority for a third control or later implementation.

## Claim and authority ceiling

After the integrated release:

- real evidence collected, parsed, accepted, authenticated, validated, or
  quarantined: `0`;
- production-validated evidence items: `0`;
- runtime evidence accepted: `0`;
- runtime prerequisites satisfied: `0 / 16`;
- production ingestion implemented/enabled: false;
- provider endpoints and credential handles/paths: `0`;
- component runtime network: false;
- external paid spend: `0`;
- runtime owner identity/decision: unbound/unrecorded;
- runtime admission, runtime authority, and provider authority: false;
- downstream gates authorized: `0 / 4`; and
- runtime side effects unlocked: `NONE`.

The local parser receipt is not a production evidence receipt, custody record,
runtime-evidence record, security review, output permit, or scientific or
application claim.

## Verification boundary

The implementation module is pure: no file, environment, clock, process,
socket, network, provider, credential, secret, randomness, entropy, or mutable
global-state I/O. The independent checker separately loads committed artifacts,
repeats the parser and envelope oracle, checks schema closure, drives the
adversarial KAT suite, freezes predecessor bytes/receipt, and verifies source
AST purity.

The frozen suite contains two positive track KATs, 64 adversarial fixture
cases (`47` direct bounded-frame cases and `17` review-entry cases), and six
pre-observation mode probes across both public frame ingress functions. Its
199 directed negatives comprise 13 envelope-identity, 48 frame/decode or
canonicalization, 25 manifest, 9 mode-separation, 72 receipt, 22 schema/strict
artifact-JSON, and 10 source-AST mutations.

The enclosing gate freezes the exact eight-path all-add source shape, file
modes, raw bytes, actual successor baseline, source/integration topology,
multiple hash seeds, deterministic output, and the preceding authorization
pack. Fast replay is non-release. Release requires one serialized integrated
full frozen-chain replay. Its successor archive contains only protected
artifacts, its immediate predecessor uses one sparse checkout, and every
successor scratch checkpoint enforces the authorized `67,108,864`-byte cap.

An independent checker is not an independent security reviewer. No reviewer,
evidence custodian, runtime owner, production rollback operator, trust-root
operator, or resource-budget authority is bound.

## Git boundary

The actual successor source baseline is
`fa0cb9f088e0da2c55c92efde860d9521d4b7493`, with tree
`7bafdda577cd79e364bac6af1b779374a3a7a52b` and sole parent
`58ab80243bc1e9484a4c4ac65dba978f35307abf`.

The source commit must have that baseline as its exact sole parent and add
exactly eight paths. Integration must be an ordinary two-parent merge whose
second parent is the source commit and whose first parent descends from the
baseline without already containing the source. Squash, rebase-shaped,
fast-forward, replace-ref, graft, mode, alias, and index-flag substitutions
fail closed.

## Next bounded unit

The predecessor's single-use implementation scope is consumed by this exact
integrated unit. The next step is a new decision, not automatic control-three
implementation:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION`

That decision must independently bound any future trust-root, signer-chain,
key-version, role, revocation, resource, reviewer, and rollback work. Until it
exists, `BOOTSTRAP_TRUST_AUTHENTICATION` remains unimplemented and no new
implementation or runtime authority is available.

## Nonclaims

This pack does not collect or process real evidence; authenticate a signature;
bind a trust root, signer, role, subject, endpoint, credential, secret, trusted
time, quarantine/custody store, replay ledger, reviewer, owner, or rollback
operator; call a provider; attempt a wire; provision paid resources; launch a
runner; inject a fault; create runtime/experiment rows; deploy; authorize an
output; or support a scientific/application claim.

It does not prove global single-use, production safety, production parser
fitness, denial-of-service resistance outside the frozen caps, or correctness
of any future authentication, semantic, freshness, custody, replay, review, or
owner-decision layer.

## Artifact binding

- Envelope schema: `e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55`
- Pure implementation: `bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1`
- Independent checker: `76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf`
- Synthetic KAT fixture: `324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9`
- Frozen expected TSV: `775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847`
- Pack manifest: `9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04`
- Predecessor reviewer: `8d3357d85513d4715553b363ebeca8ae825f92776f674ebd35acb8437c4684fa`
- Predecessor checker: `e7194d800ec811612ca7f003f1a1c29cde07ee3e9788ec8d3632c0eb4853ade0`
- Predecessor owner decision: `69e2976c1298263240e384817df3a172686e80b8a7c57359829d9e50dda5e3c3`
- Predecessor expected TSV: `cb9aca5ec6bf5fe9889d37adffb509b6249752de913356ebf4eece51993f815e`
- Predecessor manifest: `86a03cc5c97729a1b7b8ca35885e98840cb72fda44eff8a789fa9b7520de3150`
- Predecessor report: `27e7a5662fcc1861f6dfef7026389bb185854171fe81767f4c6b1c0292d3e6ea`
- Predecessor gate: `743fb03730df6e2717b95da8dfcbb8d94a2b83ba2b7442b6b2cf3d95f39a73cd`
