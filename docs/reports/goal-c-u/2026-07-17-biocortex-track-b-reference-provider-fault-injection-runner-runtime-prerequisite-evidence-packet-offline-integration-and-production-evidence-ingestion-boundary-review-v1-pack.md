# Track B runtime-prerequisite evidence offline integration and production-ingestion boundary review v1

Date: 2026-07-17
Scope: deterministic synthetic aggregate and future-boundary review only

## Outcome

`REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_OFFLINE_AGGREGATE_INTEGRATED_PRODUCTION_INGESTION_BOUNDARY_REVIEWED_RUNTIME_EVIDENCE_ZERO_NO_AUTHORITY`

The predecessor's 15 synthetic evidence-packet KATs and one pending/rejected-only
owner KAT now compose through one closed-world aggregate request. The aggregate
calls the predecessor's public validator-double API for every ordinal rather
than copying a weaker validation path. The deterministic decision is:

`OFFLINE_AGGREGATE_CONFORMANT_PRODUCTION_EVIDENCE_INGESTION_BOUNDARY_FROZEN_RUNTIME_EVIDENCE_ZERO_FAIL_CLOSED`

This is not production evidence ingestion. It receives no real bytes, binds no
endpoint, trust root, signer, credential, trusted-time source, replay ledger,
custody store, reviewer, or owner, and performs no quarantine, retention,
cleanup, provider, runner, fault, deployment, or output action.

| Measure | Value |
|---|---:|
| Tracks represented | 2 |
| Synthetic evidence packets aggregated | 15 |
| Synthetic owner packets aggregated | 1 |
| Predecessor public validator calls | 16 |
| Offline-double conformant results | 16 |
| Fixed-instant freshness arithmetic results | 15 |
| Production-ingestion controls frozen | 14 |
| Production-ingestion controls implemented | 0 |
| Threat requirements reviewed | 20 |
| Trust domains catalogued | 5 |
| Real evidence items present | 0 |
| Production-validated evidence items | 0 |
| Runtime prerequisites satisfied | 0 / 16 |
| Owner handoff eligible | false |
| Owner identity bound | false |
| Owner decision recorded | false |
| Positive decision representable | false |
| Downstream gates authorized | 0 / 4 |

## Exact offline aggregate

The request is closed-world and contains only:

- the exact request schema and version;
- mode `SYNTHETIC_FIXED_KAT_ONLY`;
- exactly 15 evidence packets in preregistration order;
- exactly one synthetic owner envelope;
- the exact frozen synthetic context hash; and
- a domain-separated, content-derived request ID.

The aggregate does not sort or repair input. Ordinal, prerequisite ID, evidence
class, owner class, track partition, packet ID, payload, predecessor binding,
freshness arithmetic, and synthetic provenance must already match the frozen
KAT. Packet 15 must bind packet IDs 1-14 in exact order, and the aggregate must
reproduce the existing domain-separated packet-set hash:

`56e9343e7e31e8a80d1a56f7ab34fc11e15412d97620c031a06f740ae29ea460`

Every packet ID must be unique and content-derived. A missing, extra, duplicate,
reordered, cross-track, stale, future-dated, rehashed, or relabelled packet
rejects the whole request. Partial success is not representable.

The owner envelope remains one of the predecessor's exact six pending or
fail-closed state/reason combinations. The normal KAT is
`PENDING_PREREQUISITE_EVIDENCE / WAITING_FOR_ALL_EVIDENCE`. In every case,
owner identity and decision recording remain false, production evidence-set
hash remains `NONE`, and approval is not representable.

## Synthetic and production domains are non-substitutable

Five domains are explicitly separated:

| Domain | Offline usable | Production implemented | Purpose |
|---|---:|---:|---|
| Synthetic packet-set v1 | true | false | Exact source-bound KAT identity only |
| Production envelope signature v1 | false | false | Future signed evidence envelope |
| Production review-subject set v1 | false | false | Future ordered validated entries 1-14 |
| Production owner-handoff set v1 | false | false | Future ordered validated entries 1-15 |
| Production owner-decision signature v1 | false | false | Future owner identity and same-set decision |

Cross-domain substitution is forbidden. In particular, the current schemas
explicitly describe synthetic validator-double packets. They cannot become
production packets by changing a label, packet kind, source field, or hash
domain. A future production path requires separate schemas, bootstrap trust,
authenticated signers, validation receipts, and domain-separated review and
owner set hashes.

## Future production-ingestion controls

The review freezes 14 mandatory future controls. Every control records
`implemented=false`, `runtime_exercised=false`, and
`satisfiable_by_offline=false`.

| # | Control | Required boundary |
|---:|---|---|
| 1 | Frame and parse | Bounded UTF-8 JSON; reject BOM, trailing bytes, duplicate keys, non-finite numbers, compression, remote references, and excessive depth |
| 2 | Mode separation | Distinct production schema, packet kind, canonicalization, and hash domains; reject every synthetic packet |
| 3 | Bootstrap authentication | Separately configured trust root, signer chain, exact key version, role, and revocation state |
| 4 | Signer authorization | Exact owner-class, evidence-class, track, subject, audience, and nonce scope |
| 5 | Track and subject binding | Exact managed/provider or self-hosted/lab profile, namespace, build, configuration, and subject |
| 6 | Quarantine and custody | Separate immutable raw-byte and canonical-payload hashes with append-only custody |
| 7 | Semantic validation | Exact schema, dependency, provenance, profile, subject, and prerequisite-specific rejection reasons |
| 8 | Trusted time and freshness | Signed time, half-open `observed <= checked < expires`, skew limits, and decision-time rechecks |
| 9 | Durable replay CAS | Linearizable single-use reservation over issuer, nonce/sequence, and raw hash |
| 10 | Validation receipt | Evidence hash, validator build/configuration, signed check time, track, prerequisite, and result |
| 11 | Independent review | Reviewer identity and role bound to entries 1-14 and validator identity |
| 12 | Owner handoff set | Separate ordered production set over validated entries 1-15 |
| 13 | Owner identity and decision | Owner role, signature, same-set hash, validation revision, and effective deadline |
| 14 | Decision and downstream separation | Atomic single-use owner-decision CAS; four downstream gates remain separate |

The bootstrap boundary matters: evidence for the authority verifier and trust
root cannot authenticate itself. Likewise, evidence intended to prove the
replay ledger or custody store may enter only bounded quarantine until an
independent bootstrap verifier and store are already available. Offline
conformance cannot close either bootstrap loop.

## Freshness and owner-window rules

The production policy is frozen as a requirement, not exercised:

| Packet | Maximum age | Additional rule |
|---:|---:|---|
| 6 | 86,400 s | Recheck exact endpoint/profile/region/namespace/TLS/track at decision |
| 7 | 3,600 s | Recheck scope and prove zero active lease commitments |
| 8 | 86,400 s | Recheck resource scope, cost ceiling, budget owner, and auto-stop policy |
| 10 | 300 s | Recheck signed time, skew, row epoch, and currentness |
| 12 | 604,800 s | Preserve exact runner-build identity |
| 13 | 604,800 s | Preserve exact storage-policy identity |
| 16 | 1,800 s | Decision deadline is the minimum of the owner window and every bounded evidence expiry |

All other packets require exact build, configuration, identity, schedule, or
set binding rather than a fabricated age. The predecessor's
`NO_MAX_AGE_KAT_HORIZON_SECONDS=31536000` is only a synthetic construction
horizon and is not a one-year production lifetime.

Any decision-time recheck that changes content, a validation receipt, or an
entry hash invalidates the set and requires a new ordered production set,
independent review, and final validation.

## Threat requirements

Twenty fail-closed requirements cover:

- framing, parser differential, schema, and synthetic/production type confusion;
- invalid signatures, untrusted or revoked keys, signer authorization, and
  audience/context mismatch;
- managed/self-hosted substitution and subject/build/profile/session drift;
- raw/canonical/packet-ID divergence;
- stale, future-dated, skewed, or owner-window-expired evidence;
- replay and concurrent non-atomic replay races;
- missing, duplicate, reordered, or substituted review and owner-set entries;
- custody, retention, cleanup, or tombstone divergence;
- reviewer non-independence or validator-build drift; and
- premature positive authority.

These are review requirements, not observed production rejections. No
production attack case was executed, no item entered quarantine, and no
security approval was issued.

## Owner handoff remains blocked

A future handoff candidate would require all of the following at once:

1. exactly 15 unique, ordered, production-validated evidence entries;
2. a production review-subject set over validated entries 1-14;
3. a separate production owner set over validated entries 1-15;
4. per-entry binding to prerequisite, track, subject, packet, and validation receipt;
5. signed final-validation time and all required rechecks;
6. an independent reviewer bound to the same set and validator build/configuration;
7. authenticated owner identity, role, audience, and signature;
8. an unchanged set through the effective decision deadline;
9. an atomic single-use decision-ledger revision; and
10. independent evaluation of the four downstream gates.

The current owner schema cannot represent a positive decision. A future
positive path would require an independently reviewed successor production
schema and explicit owner authority. The aggregate receipt is not a handoff
candidate, evidence receipt, execution authority, output permit, runtime
admission, or security approval.

## Independent falsification

The independent checker reloads the exact predecessor artifacts, generates the
known-answer aggregate, calls all 16 predecessor public validator APIs, and
recomputes the packet-set, case-result, request, fixture, nonclaim, and receipt
hashes. It enforces duplicate-safe finite JSON, closed-world fixture catalogs,
source-AST purity, an exact public API, deterministic TSV, and directed
mutations across aggregate order/cardinality/identity, owner state matrix,
trust domains, controls, threats, freshness, handoff, nonclaims, and receipt
boundaries.

The enclosing shell gate freezes the exact source commit shape, seven-path
all-add delta, file modes, raw bytes, source/integration topology, clean index
and worktree, deterministic output under multiple hash seeds, and the entire
frozen predecessor chain.

## Git and replay boundary

The exact source baseline is
`3d03193b645ded944b10a310633be8d6a2c1ab1b`, with tree
`320bc06806d033e3304c2f5edf80667f36c21a40` and parents
`d7f3e206169227905dbd320f1876de46e3facfea` then
`151c3294c92e79759401cf86e8f36263bbf17ade`.

A source commit must have that exact sole parent and add exactly seven paths.
Integration must be an ordinary two-parent merge whose second parent is the
source commit and whose first parent descends from the baseline without already
containing the source. Squash, rebase-shaped, fast-forward, replace-ref, graft,
mode, alias, and index-flag substitutions fail closed.

The gate executes the frozen predecessor gate directly in an isolated clone.
It does not wrap it in another mount namespace because the frozen predecessor
already establishes its own no-network namespace for deeper replay, and nested
namespace creation is not supported on the validation host. New gate scratch
uses a private persistent POSIX directory to avoid tmpfs OOM pressure. Fast
validation is non-release; release requires one serialized full frozen-chain
replay.

## Nonclaims

The 52-field closed-world nonclaim record keeps all production, evidence,
authority, owner, runner, output, and deployment claims false and
`side_effects_unlocked=NONE`. In particular, this unit does not:

- implement a production packet schema, endpoint, authenticator, validator,
  trust bootstrap, custody store, replay ledger, or trusted-time binding;
- collect, ingest, authenticate, validate, accept, retain, quarantine, replay,
  or clean up real evidence;
- bind a provider, lab, endpoint, profile, credential, key, resource, budget,
  reviewer, custodian, or owner;
- prove real currentness or satisfy any runtime prerequisite;
- launch a runner, inject a fault, create runtime/experiment rows, deploy, or
  write Agent-Bridge memory as experiment output;
- record an owner decision or represent a positive decision;
- grant runtime admission, condition output, output permit, scientific claim,
  application claim, or any side effect.

S16 remains adjacent synthetic durability currentness only. It is neither this
unit's Git predecessor nor production runner evidence and cannot satisfy any
ingestion control or prerequisite.

## Deterministic receipt

```text
tracks_represented=2
evidence_packet_count=15
owner_packet_count=1
aggregate_case_result_count=16
offline_double_conformant_count=16
freshness_arithmetic_conformant_count=15
dependency_topology_conformant=true
track_separation_conformant=true
production_ingestion_control_count=14
production_ingestion_controls_implemented=0
threat_case_count=20
trust_domain_count=5
owner_handoff_requirement_count=10
real_evidence_items_present=0
production_validated_evidence_items=0
runtime_prerequisites_satisfied=0
owner_handoff_eligible=false
owner_identity_bound=false
owner_decision_recorded=false
positive_decision_representable=false
runtime_admission_granted=false
runtime_authority=false
downstream_gates_authorized=0
side_effects_unlocked=NONE
synthetic_packet_set_sha256=56e9343e7e31e8a80d1a56f7ab34fc11e15412d97620c031a06f740ae29ea460
content_sha256=7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa
```

## Next boundary

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_INGESTION_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION`

The offline preparation line is complete at the review boundary. The next
step is an explicit owner/resource decision, not another synthetic evidence
claim. It must choose an authorized production or isolated-lab implementation
scope and bind responsible identities, trust bootstrap, endpoint/resource
limits, credentials, cost ceiling, trusted time, custody, replay ledger,
reviewer, and rollback authority before implementation or evidence collection.
Absent that decision, runtime admission remains blocked and side effects remain
`NONE`.

## Artifact binding

- Reviewer source: `a2fa9559b43413e1c729d58b89f1ec951c6722ab142f0a3be4f7c6cdd98d9530`
- Independent checker: `4fac8a588980811e12f4b324c31a9f42d70f683051555560924932c235eb1c45`
- Synthetic boundary fixture: `3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6`
- Frozen expected TSV: `70fbf15cc210fb365b5377642c49d91fa00a2a049affeeec595ef76dd1bf3234`
- Pack manifest: `59260f9d4d5e00924739f96de567695dfe326413a01fcb3600703d9efb945b54`
- Predecessor evidence schema bytes: `121c66331f159539722acb8f173696811487d8b76b9da07ab9d83340e28277d3`
- Predecessor owner schema bytes: `7845de2ac7d1f069fd550f5625a1593c0a093563acbe1be1855bf7df0f3d4436`
- Predecessor reviewer bytes: `29a4b67049429c09981f1742f072a3fe382f381259fa238b69041b3d46939351`
- Predecessor manifest bytes: `c5d448a121b58549a62e20ec7b241386ad73c9685ae9a981223a591555e2bd47`
- Predecessor gate bytes: `df47afdefdf04bf6e82f29a7b867543edfb511d3d124a095a2e998eb8c72cbe0`
