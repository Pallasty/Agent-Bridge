# Track B production-evidence ingestion implementation authority and resource-binding decision v1

Date: 2026-07-17

## Outcome

`REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_ISOLATED_LAB_FIRST_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_NO_RUNTIME_OR_PROVIDER_AUTHORITY`

The owner-facing direction to continue after the recommended
`ISOLATED_LAB_FIRST` path authorizes one exact, reversible, local repository
implementation unit. The decision is:

`AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED`

This is implementation-code authority, not runtime authority. It permits only
the next bounded frame-parser and synthetic/production mode-separation
component, its schemas, fixtures, tests, checker, report, and source-bound Git
gate. It does not authorize production enablement, evidence ingestion,
provider access, a runner, a fault, a deployment, or any downstream output or
claim.

## Three authority planes remain separate

| Plane | Current state | Meaning |
|---|---|---|
| Planning direction | `ISOLATED_LAB_FIRST` confirmed | Continue the recommended sequence before any production path |
| Exact implementation unit | local code-only authority recorded | Reversible repository work for one named successor only |
| Runtime / provider / production | not authorized | No endpoint, credential, evidence, execution, or activation authority |

The exact implementation scope is
`ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_SINGLE_USE_NON_TRANSITIVE`. It cannot
be reused for a later control, another branch, an endpoint, a lab process, or a
runtime experiment. The future successor must remain default-off and offline;
it must obtain a new decision before any scope expansion.

## Owner-label semantics

The semantic actor label is `pallasting`, with role label `PROJECT_OWNER`, from
the established project profile and current-session continuity. This records
who supplied the project direction at the conversational layer. It does not
claim cryptographic authentication:

- no signature was observed;
- no key, credential, or identity proof was accessed;
- runtime owner identity and role remain unbound;
- no runtime owner decision was recorded; and
- no agent may substitute this label for a signed production decision.

The distinction is deliberate. Repository implementation permission can be
grounded in the owner's established reversible-work autonomy and the immediate
instruction to continue. Runtime admission still requires the separate
production owner-handoff protocol and all 16 validated prerequisites.

## Resource binding is fail-closed

The implementation resource binding is closed at the resource-class and cap
level. It permits only existing local CPU and RAM, one isolated Agent-Bridge
worktree for the exact successor, committed non-secret fixtures, private local
test scratch, and deterministic offline standard-library execution. The
component caps one worker, 64 MiB of private scratch, a 1 MiB input frame, 32
JSON levels, 256 object members, and 64 array items.

The current branch and worktree are the source-bound packaging locus for this
decision, not a reusable runtime resource grant. The successor's own source
gate must bind its actual Git baseline and isolated worktree after this
decision is integrated; it may not treat the current packaging path as
transitive authority.

External paid spend is capped at zero across all currencies. Zero is a
fail-closed agent default under the owner's reversible-work policy; it is not
represented as an owner-supplied numeric budget or as evidence that budget
authority was bound.

All provider endpoint lists, credential handles, credential paths, production
trust roots, signer identities, secret material, trusted-time sources,
quarantine stores, custody stores, and durable replay ledgers are empty. The
component runtime network allowance is false. The isolated-lab sequence has
been selected, but no lab endpoint or runtime profile is bound yet.

## Exact authorized successor

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_ENVELOPE_BOUNDED_FRAME_PARSER_AND_SYNTHETIC_MODE_SEPARATION_ISOLATED_LAB_IMPLEMENTATION`

Only two candidate control surfaces are authorized for code:

1. bounded frame parsing; and
2. synthetic/production mode separation.

The successor may define closed-world envelope framing, byte/depth limits,
duplicate/non-finite rejection, explicit packet kinds, and domain separation.
It may exercise deterministic local KATs and rejection cases. It may not
authenticate a real signer, contact a provider, open a socket, accept real
evidence, persist quarantine data, claim trusted time, or implement any of the
remaining twelve production-ingestion controls.

Authorization does not mean implementation. At this decision checkpoint,
candidate controls implemented remain `0 / 14`, candidate controls
runtime-exercised remain `0 / 14`, and real evidence remains zero.

## State machine

The closed-world implementation-authority states are:

```text
UNRECORDED_NO_AUTHORITY
  -> AUTHORIZED_ISOLATED_LAB_FIRST_EXACT_UNIT
  -> CONSUMED_SCOPE_COMPLETE
  -> INVALIDATED_REQUIRES_NEW_DECISION

UNRECORDED_NO_AUTHORITY
  -> REJECTED_FAIL_CLOSED
```

There is no positive runtime-authority state. Owner revocation or drift in the
baseline, successor identity, allowed operations, resource classes or caps,
network policy, credentials, endpoints, or side-effect surface invalidates the
authorization and requires a new decision. Completion consumes the exact unit;
it does not make this authority transitive.

## Rollback

Before merge, rollback is deletion of the isolated worktree and branch. After
merge, rollback is an ordinary Git revert of the exact source/integration
change. The successor must remain reproducible from committed fixtures and
must not require external cleanup. This is local repository rollback only; no
production rollback operator or production cleanup authority is bound.

## Verification boundary

The pure reviewer accepts one exact real decision record in memory and emits a
content-derived receipt. It performs no file, environment, clock, process,
network, provider, credential, randomness, or mutable-state I/O. The
independent checker performs duplicate-safe finite JSON loading, repeats the
closed-world authority/resource/state/hash checks, rejects overclaim
mutations, freezes predecessor artifacts, and verifies source AST purity.

The enclosing gate freezes the exact seven-path all-add source shape, file
modes, raw bytes, source/integration topology, clean worktree/index, multiple
hash seeds, deterministic output, and the predecessor's complete source-bound
chain. Fast replay is non-release; one serialized integrated full replay is
required for release evidence.

An independent checker is not an independent security reviewer. Reviewer,
runtime owner, evidence custodian, production rollback operator, and resource
budget authority remain unbound.

## Claim and authority ceiling

After this decision:

- production-ingestion controls implemented: `0 / 14`;
- real evidence items: `0`;
- production-validated evidence items: `0`;
- runtime prerequisites satisfied: `0 / 16`;
- production review-subject set: `NONE`;
- owner-handoff set: `NONE`;
- runtime owner decision recorded: false;
- runtime admission: false;
- runtime authority: false;
- provider authority: false;
- downstream gates authorized: `0 / 4`; and
- runtime side effects unlocked: `NONE`.

The only positive authority is
`REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY`.

## Git boundary

The exact source baseline is
`d5bbe55d5d95b1163e287415f437cf77c594135d`, with tree
`6fd22d3e8abba06ae5eab26c9c9ce2af5672ada9` and parents
`3d03193b645ded944b10a310633be8d6a2c1ab1b` then
`0268990ee74a6a958269d1c07f7d575d0284e6bf`.

A source commit must have the baseline as its exact sole parent and add exactly
seven paths. Integration must be an ordinary two-parent merge whose second
parent is that source commit and whose first parent descends from the baseline
without already containing the source. Squash, rebase-shaped, fast-forward,
replace-ref, graft, mode, alias, and index-flag substitutions fail closed.

## Nonclaims

The machine-readable record explicitly denies production ingestion and
enablement; real evidence collection, ingestion, authentication, validation,
acceptance, or quarantine; endpoint, credential, trust-root, signer,
trusted-time, custody, replay, reviewer, and production rollback binding;
provider calls, wire attempts, paid resource provisioning, runner launch,
fault injection, deployment, runtime or experiment rows, output permits, and
scientific or application claims.

It also records that zero budget is not a resource reservation, the semantic
owner label is not an authenticated identity, the independent checker is not a
security approval, global single-use has not been proved, and this decision
does not derive Git publication authority.

## Artifact binding

- Reviewer source: `8d3357d85513d4715553b363ebeca8ae825f92776f674ebd35acb8437c4684fa`
- Independent checker: `e7194d800ec811612ca7f003f1a1c29cde07ee3e9788ec8d3632c0eb4853ade0`
- Owner implementation decision record: `69e2976c1298263240e384817df3a172686e80b8a7c57359829d9e50dda5e3c3`
- Frozen expected TSV: `cb9aca5ec6bf5fe9889d37adffb509b6249752de913356ebf4eece51993f815e`
- Pack manifest: `86a03cc5c97729a1b7b8ca35885e98840cb72fda44eff8a789fa9b7520de3150`
- Predecessor reviewer: `a2fa9559b43413e1c729d58b89f1ec951c6722ab142f0a3be4f7c6cdd98d9530`
- Predecessor checker: `4fac8a588980811e12f4b324c31a9f42d70f683051555560924932c235eb1c45`
- Predecessor boundary fixture: `3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`
- Predecessor expected TSV: `70fbf15cc210fb365b5377642c49d91fa00a2a049affeeec595ef76dd1bf3234`
- Predecessor manifest: `59260f9d4d5e00924739f96de567695dfe326413a01fcb3600703d9efb945b54`
- Predecessor report: `a91d98e79cc33d9752229fccdf818b9a8f8d9e0d0c427b431ac1dc00434544b3`
- Predecessor gate: `e2a3e5fd49ebd58697838bc3f7e1860ce511f225a4bdd11ac8f2772bd8087cf7`
