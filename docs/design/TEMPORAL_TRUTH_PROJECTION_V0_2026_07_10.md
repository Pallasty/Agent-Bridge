# Temporal Truth Projection v0

Date: 2026-07-10
Status: implementation contract — pure, read-only, shadow-only
Owner: Agent-Bridge memory plane

## Decision

Agent-Bridge needs a claim-level temporal truth projection before it needs
another digest, global graph prior, ANN index, or BioCortex retrieval path.
The portfolio-continuity successor trial reduced estimated context tokens by
79.9529% but returned `NO_ADVANCE`: the compact condition was materially stale,
misbound adjacent referents, and omitted required support. Full hybrid retrieval
also missed the strict currentness/unsupported-assertion gate.

The first implementation slice is therefore a deterministic pure resolver. It
does not search, write, rank, cache, register an MCP tool, or change runtime
behavior. Callers must provide explicit normalized claim evidence. The resolver
returns a claim projection or rejects structurally unsafe input.

## Authority boundary

Agent-Bridge is authoritative about:

- which evidence exists and which claim it describes;
- the evidence's observed time, validity, lifecycle, provenance, and explicit
  supersession/invalidation relationships;
- whether the best available result is supported, conflicted, historical,
  future, indeterminate, or unknown.

"Authoritative" does not mean that every memory is true. `unknown` and
`conflicted` are first-class authoritative outcomes.

BioCortex, if admitted by a later corpus gate, may only propose short-lived
context actions over an opaque projection. It may not create claims, upgrade
truth state, resolve conflict, write memory, change retrieval order, or execute
a context rollover.

## v0 input contract

The resolver receives:

```text
as_of
knowledge_cutoff
required_claims[] = (referent_id, predicate_id)
evidence[]:
  evidence_id
  lineage_id
  claim:
    referent_id
    predicate_id
  aliases[]
  value
  observed_at
  recorded_at
  validity = timeless | bounded(valid_from, valid_until) | indeterminate
  lifecycle = active
            | superseded(effective_from)
            | archived(effective_from)
            | tombstoned
  truth_tier = authoritative | verified | observed | inferred
  source_keys[]
  supersedes[] = (target_lineage_id, effective_from)
  invalidates[] = (target_lineage_id, effective_from)
```

`referent_id` identifies the described object. `predicate_id` identifies the
property asserted about that object. A memory key is evidence identity, not
referent identity.

`knowledge_cutoff` is distinct from `as_of`:

- `as_of`: world time the answer describes;
- `knowledge_cutoff`: latest Agent-Bridge admission time the resolver may use.

`observed_at` is the world time of the source observation. `recorded_at` is the
knowledge time at which Agent-Bridge admitted the complete immutable envelope.
v0 requires `as_of <= knowledge_cutoff`. Evidence with `recorded_at` after the
knowledge cutoff is excluded and cannot change projection content, serialized
output, or success/failure. This prevents a later backfill about an earlier
world event from leaking into a historical knowledge view.

An evidence envelope is immutable. Revisions of the same logical evidence keep
one stable `lineage_id`; relationship endpoints name that lineage rather than a
particular evidence revision. Any change to value, validity, lifecycle, tier,
sources, aliases, or relationships must create a new revision with a new
evidence id and `recorded_at`. Updating an old row in place would invalidate the
knowledge-cutoff guarantee and is forbidden for future adapters.

Each revision is a full snapshot. At a knowledge cutoff the resolver selects the
latest visible revision in each lineage. Claim identity is immutable within a
lineage. Once a relationship is declared, every later revision must carry it
forward, including before a scheduled `effective_from`; cancellation requires a
new, versioned governance model rather than silently dropping the edge. Claim
drift, a missing durable relationship, or two revisions in one lineage with the
same `recorded_at` all fail closed. Because the current store uses second-level
timestamps, a future adapter must guarantee a unique monotonic `recorded_at` per
lineage or introduce a separately reviewed revision sequence before admission.

A tombstone carries the target `lineage_id` and retroactively redacts every
revision in that lineage before knowledge-view selection. Inbound relationships
to a redacted target are pruned because they no longer govern any visible
evidence. A redacted source lineage that ever declared a durable relationship
instead fails the entire request closed; deleting a correction must never
silently resurrect its target. This is the single intentional exception to
cutoff non-interference: privacy deletion outranks historical replay. Tombstone
authority and lineage mapping remain the responsibility of an
Agent-Bridge-owned adapter; an untrusted caller may not mint a tombstone.

These guarantees have a hard adapter precondition: the normalized request must
contain the complete revision history for every supplied lineage, the complete
tombstone index irrespective of `knowledge_cutoff`, and relationship endpoint
closure for the permitted knowledge view. The pure resolver cannot infer
history that an adapter physically omitted. If raw source revisions have been
deleted for privacy, a later adapter/schema must retain a content-free
`had_durable_governance` attestation or equivalent opaque relationship metadata;
until that exists, such a source must not be adapted. `TombstonedGovernanceSource`
is therefore a fail-closed detector under a complete input, not a self-contained
proof that omitted history never existed.

### Validity boundary

For compatibility with the frozen portfolio-continuity evaluator, bounded
validity is inclusive:

```text
valid_from <= as_of <= valid_until
```

Either bound may be absent. A future schema that wants half-open intervals must
use a differently named field and a version bump; v0 must not silently change
the evaluator's established boundary semantics.

`timeless` is an explicit caller claim. Missing temporal knowledge must be
encoded as `indeterminate`, never silently promoted to timeless/current.

## Structural fail-closed rules

The entire request is rejected when any of these holds:

- negative or inverted request/evidence timestamps;
- `observed_at > recorded_at`;
- empty, non-ASCII, control-bearing, or oversized machine labels;
- duplicate required claims or evidence ids;
- multiple revisions in one lineage with the same `recorded_at`;
- claim identity drift within a lineage;
- a later lineage revision dropping a previously declared relationship;
- empty evidence value or source list;
- invalid bounded interval;
- `bounded` validity without either bound (callers must choose `timeless` or
  `indeterminate` explicitly);
- alias collision across canonical referents;
- dangling, self-referential, or cyclic supersession/invalidation;
- indeterminate evidence attempting to carry a truth relationship;
- a relationship becoming effective outside its source's active validity or
  lifecycle interval;
- duplicate relationships to one target with different effective times;
- declaring both `supersedes` and `invalidates` from one source to one target;
- a relationship crossing `(referent_id, predicate_id)`;
- a lower-tier source attempting to suppress higher-tier evidence.
- a privacy-redacted source lineage carrying durable governance relationships.

These are integrity failures, not `unknown` evidence. v0 does not guess around
them or accept only the apparently healthy rows.

## Resolution semantics

1. Apply tombstone lineage redaction, then select the latest permitted revision
   per lineage using immutable-envelope `recorded_at`. Cutoff-excluded evidence
   has no observable effect; a tombstone intentionally removes its entire
   lineage even when the requested historical cutoff predates the deletion.
2. Validate and canonicalize all visible labels and relationship endpoints.
3. Apply explicit same-claim supersession/invalidation only from each
   relationship's `effective_from`. Before that world-time boundary the target
   remains eligible. Once declared, the relationship must be carried by later
   lineage revisions; once effective, it persists as a governance fact even
   when its source later becomes historical. A source suppressed by an earlier
   incoming relationship cannot fire a later outgoing relationship.
4. Derive each remaining evidence item's temporal state:
   - superseded/archived at or after its lifecycle `effective_from`, or
     explicitly suppressed at or after a relationship `effective_from` ->
     `historical`;
   - before a lifecycle transition's `effective_from`, evaluate the evidence as
     active so historical `as_of` replay remains correct;
   - timeless active -> `current`;
   - bounded active and before its interval -> `future`;
   - bounded active and inside its interval -> `current`;
   - bounded active and after its interval -> `historical`;
   - indeterminate active -> `indeterminate`.
5. For each requested or discovered claim, select the first non-empty temporal
   class in this order: `current`, `indeterminate`, `future`, `historical`.
6. Inside that class, the highest truth tier is load-bearing. One distinct
   top-tier value yields `supported`; multiple distinct top-tier values yield
   `conflicted`. Lower-tier agreement remains supporting evidence; lower-tier
   disagreement is retained as shadowed evidence and cannot silently win.
7. A required claim with no visible evidence yields
   `truth_state=unknown`, `temporal_state=indeterminate`.

Output ordering is canonical and independent of input order.

## v0 output contract

```text
schema = agent_bridge.truth_projection.v0
mode = shadow_only
as_of
knowledge_cutoff
claims[]:
  referent_id
  predicate_id
  aliases[]
  truth_state = supported | conflicted | unknown
  temporal_state = current | historical | future | indeterminate
  truth_tier?
  values[]
  evidence_ids[]
  supporting_evidence_ids[]
  shadowed_evidence_ids[]
  noncurrent_evidence_ids[]
  evidence_dispositions[]:
    evidence_id
    temporal_state
    reasons[] = active | not_yet_valid | validity_expired
              | indeterminate_validity | lifecycle_superseded
              | lifecycle_archived | superseded_by | invalidated_by
  source_keys[]
```

This internal v0 output still contains evidence ids and values. It must not be
sent directly to BioCortex. A future cross-repository transport must replace
raw ids/content with per-request opaque handles, bind the projection to a
snapshot/HMAC, prohibit persistence/network egress, and carry hard-false
runtime authority invariants.

The raw module is crate-private. Only an Agent-Bridge-owned adapter may assign a
`truth_tier`, and that assignment must come from a predicate-scoped authority
policy rather than a self-declared memory tag or caller-provided score. The
resolver trusts its normalized input; it is not itself an authorization or
privacy boundary.

## Acceptance gate

The pure resolver must cover at least these adversarial classes:

1. current claim;
2. expired historical claim;
3. not-yet-valid future claim;
4. indeterminate validity;
5. explicit supersession chain;
6. explicit invalidation;
7. same-tier conflict;
8. higher-tier truth hierarchy;
9. unknown required claim/abstention;
10. same referent with different predicates;
11. alias collision rejection;
12. dangling relationship rejection;
13. relationship cycle rejection;
14. lower-tier suppression rejection;
15. knowledge-cutoff future-leak prevention;
16. late backfill and tombstone non-interference;
17. lifecycle transition historical replay;
18. relationship effective-time historical replay;
19. suppression-chain ordering (a suppressed source cannot fire later);
20. inclusive `as_of` boundaries;
21. byte-identical serialization after input permutation;
22. explicit evidence-disposition reasons;
23. dual relationship-kind and conflicting-time rejection;
24. non-ASCII alias rejection;
25. tombstone lineage redaction, including older active revisions;
26. strict JSON unknown-field rejection.
27. latest-revision selection and ambiguous same-time revision rejection;
28. immutable lineage claim identity and durable relationship carry-forward;
29. redacted-target edge pruning and redacted governance-source failure.

Focused verification must pass with zero database, graph, coactivation, query
log, retrieval surfacing, access-stat, MCP registry, or default-profile change.

## BioCortex corpus gate

The existing BioCortex temporal adapter remains healthy, but it is not a
boundary-aware context gate. Agent-Bridge's event spine is a plausible real
event source; the current snapshot is not a qualified corpus because tool
outcomes lack reliable episode/context linkage and raw facts may contain paths,
messages, arguments, or output previews. The inspected live snapshot also had
too few outcome-bearing negative episodes to support the frozen comparison, so
mechanism implementation is stopped rather than backfilled with a synthetic
winner.

Do not add a BioCortex trace-bank or context-gate mechanism until a separate,
privacy-reviewed exporter can produce:

- stable opaque episode ids and monotonic sequence;
- bucketed/capped inter-event delays;
- bounded source/kind classes;
- explicit boundary hints and externally verified outcome classes;
- episode/time-separated train, validation, and test partitions;
- a recomputable fixture hash and a zero-hit raw-field leak scan;
- enough positive, negative, jitter, missing-boundary, and context-switch cases
  to compare a hard-boundary state machine, a single-EWMA reduction, and a
  multi-timescale candidate without a trivial winner.

If corpus qualification fails, the BioCortex implementation remains stopped.
If direct math ties or wins, record `NO-GO` (or `HOSTED` when supplied boundary
labels do all useful work) and do not ship the biological candidate.

## Later slices (not authorized by v0)

1. A side-effect-free exact evidence reader (`memory_peek`) with mutation
   counters proving zero access/query/coactivation telemetry.
2. An opt-in, Niche-profile assembler tool over explicit truth bindings.
   Before accepting untrusted/MCP input, add hard caps for required claims,
   visible evidence, aliases, source keys, relationships, and serialized bytes;
   invalid-request error ordering must also be canonicalized.
3. Adaptive evidence budgeting after truth quality passes the frozen strict
   gate.
4. Opaque-handle BioCortex shadow transport after corpus qualification.

No later slice may reuse `memory_get` or current hybrid MCP paths while claiming
to be read-only: those paths update access/retrieval telemetry today.
