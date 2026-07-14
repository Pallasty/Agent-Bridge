# BioCortex × Agent-Bridge Track B exact-artifact dependency graph

Date: 2026-07-14

Baseline: `3840fc214118f692d37a54e6abdd46ab192080ad`

Decision: `PLANNING_GRAPH_VALIDATED_FAIL_CLOSED`

## Result first

The 23 `EXACT_COMMITTED_ARTIFACT_ONLY` scalar paths now have a frozen,
machine-checked dependency graph.  The graph identifies 13 artifacts whose
public semantics can be designed without choosing owner policy, reading
private custodian material, or inventing a missing upstream interface.  The
remaining ten split into six owner-policy-dependent, two
custodian-private-dependent, and two upstream/runtime-dependent artifacts.

This is an implementation-planning result, not an admission result.  No new
artifact bytes, repository path, blob OID, or live binding evidence exists in
this packet.  Committed artifact count, implementation-ready count,
live-binding-ready count, and unlocked side effects all remain zero.

The graph is stored in
`scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json`.
Its source inventory is the 91-row live-binding ledger, whose 23 exact-artifact
rows are all local deterministic SHA-256 bindings at pre-output admission
while still unsatisfied and evidence-free.  The old successor-v3 mechanisms
remain mechanism-only; their cases, reviewer roster, maps, receipts, results,
and hashes cannot satisfy a new Track B binding.

## Classification rule

The graph answers one narrow question: **can the exact source artifact be
publicly designed and frozen now without making an unauthorized semantic
choice?**  It does not attempt to repeat the full real-run input closure.
That closure remains the preceding ledger's 91 scalar bindings plus four
stage obligations.

This distinction prevents two opposite errors:

- a real seed, snapshot, reviewer response, hardware profile, or manifest can
  be a required execution instance without blocking a provider-neutral schema
  or pure algorithm from being authored;
- a generic wrapper is not an exact artifact when owner policy, a fresh
  provider/roster profile, or an upstream object schema still determines its
  behavior.

The primary controlling class is selected in this order: an explicitly
blocked or unrepresented upstream interface, fresh custodian semantics,
owner policy, runtime-only semantics, then no blocker.  A node is publicly
authoring-eligible only when its primary class is `INDEPENDENT_PUBLIC` and
all of its local artifact dependencies are also eligible.

## Exact 23-node decision matrix

| Binding path | Class | Direct semantic dependency or reason |
|---|---|---|
| `context_and_result.context_builder_sha256` | upstream/runtime | candidate builder plus an unrepresented candidate evidence-substrate interface; exact budgets; tokenizer and reference builders |
| `context_and_result.exact_tokenizer_code_sha256` | owner policy | owner-selected tokenizer identity and matching exact model bytes |
| `generation.harness_sha256` | owner policy | condition rosters, execution profile, instruction; shared context and blind-map checker |
| `latency.runner_sha256` | owner policy | affinity, hardware-guard, and timeout policies; shared context builder |
| `power_and_estimator.paired_method_sha256` | owner policy | cluster-variance policy; strict-case algorithm and sampling-receipt schema |
| `reference_condition.context_builder_sha256` | independent public | provider-neutral wrapper can accept later frozen config; S0 is mechanism evidence only |
| `review_and_blinding.map_bijection_checker_sha256` | independent public | map schema and sampling-receipt schema |
| `review_and_blinding.map_schema_sha256` | independent public | public identity fields are already frozen; private values are later instances |
| `review_and_blinding.review_command_schema_sha256` | independent public | must remain provider-neutral; roster-specific argv belongs to later provenance enforcement |
| `review_and_blinding.review_provenance_checker_sha256` | custodian private | fresh reviewer roster and conflict/overlap profile, plus review instruction and the three review-chain artifacts |
| `review_and_blinding.review_raw_response_schema_sha256` | custodian private | raw provider boundary depends on the fresh reviewer/provider profile |
| `review_and_blinding.review_receipt_schema_sha256` | independent public | provider-neutral command and review schemas; raw bytes remain opaque and hash-bound |
| `review_and_blinding.review_schema_sha256` | independent public | referent schema and already-frozen reviewer gates |
| `sampling.frame_builder_sha256` | owner policy | population, window, and inclusion/exclusion semantics |
| `sampling.pilot_confirmatory_disjointness_checker_sha256` | owner policy | overlap grain depends on population and inclusion/exclusion policy; frame builder and selection algorithm |
| `sampling.sampling_receipt_schema_sha256` | independent public | 18 required identity and probability/weight bindings are public and frozen |
| `sampling.sampling_receipt_writer_sha256` | independent public | receipt schema, seed derivation, selection algorithm, and fail-closed no-overwrite semantics |
| `sampling.sampling_seed_derivation_sha256` | independent public | domain, message, anti-shopping order, and separation rule are public and frozen |
| `sampling.sampling_selection_algorithm_sha256` | independent public | stratified HMAC ordering and exact weight rule are public and frozen |
| `storage.serializer_sha256` | upstream/runtime | canonical memory/edge object schema is not represented by a live binding; transport JSONL is not a valid substitute |
| `truth_inputs.referent_schema_sha256` | independent public | opaque referent/predicate identity can be policy-parameterized without exposing AB source keys |
| `truth_inputs.strict_case_algorithm_sha256` | independent public | review schema and truth-manifest schema; all AND gates and thresholds are frozen |
| `truth_inputs.truth_manifest_schema_sha256` | independent public | referent schema; authority policy remains a later hash-bound instance, not a schema-authored choice |

## Public authoring topology

The independent subgraph has three waves:

1. Seven roots: reference context builder, blind-map schema, provider-neutral
   review-command schema, sampling-receipt schema, seed derivation, selection
   algorithm, and referent schema.
2. Four compositions: map bijection checker, review schema,
   sampling-receipt writer, and truth-manifest schema.
3. Two integrity artifacts: review-receipt schema and strict-case algorithm.

The recommended first implementation pack is intentionally smaller than the
seven-node frontier:

- `review_and_blinding.map_schema_sha256`
- `review_and_blinding.review_command_schema_sha256`
- `sampling.sampling_receipt_schema_sha256`
- `truth_inputs.referent_schema_sha256`

These four provider-neutral schemas create the identity spine used by later
checkers and algorithms while avoiding the larger reference-wrapper and
cryptographic-algorithm changes in the same review packet.  Each should be a
separate exact artifact with canonical bytes and adversarial fixtures.
Finishing that pack will change source-artifact status only; a later admission
packet must still bind the exact hashes together with all owner, custodian,
runtime, and stage inputs.

## Data-quality assessment

Intended use and grain are explicit: one graph row per exact-artifact scalar
binding, used only to schedule source implementation.  Completeness is checked
by set equality against all 23 ledger rows, not by count alone.  Uniqueness and
validity checks cover canonical JSON, duplicate keys, sorted unique paths,
known dependency targets, exact ledger owner/fill projections, and null
artifact evidence.  Referential integrity is checked with a complete DAG,
lexical topological order, independently derived waves, and rejection of
redundant transitive edges.  Timeliness is source-bound to the live ledger
commit rather than the earlier drifted Track B source snapshot.

The main residual limitation is semantic rather than mechanical: an exact
dependency edge cannot be inferred from field names alone.  The per-node
mapping is therefore frozen by a catalog hash and independently reviewed;
the checker separately derives coverage, classes, eligibility, waves, and
counts so those outputs cannot be trusted merely because the JSON reports
them.  Two missing interfaces are explicitly recorded rather than hidden:
the candidate evidence-substrate interface and the canonical memory/edge
object schema.

## Enforcement and non-authority boundary

The strict checker rejects missing or substituted nodes, illegal external or
upstream references, cycles, false readiness, non-null artifact evidence,
authority changes, source drift, and evidence substitution.  Its adversarial
self-test contains 48 graph/source mutations.  The shell gate runs twice from
immutable Git blobs, compares the output byte-for-byte with the fixed receipt,
checks exact Git modes and OIDs, and requires the packet source commit to
directly parent the frozen ledger commit.  Replace refs, legacy grafts, and
shallow history are rejected; the parent is read from the raw commit object.

A successful gate still reports:

```text
committed_artifact_count=0
implementation_ready_count=0
live_binding_ready_count=0
artifact_binding_complete=false
real_run_admitted=false
side_effects_unlocked=NONE
```

It does not authorize private reads, runtime execution, capture, generation,
review, unblinding, scoring, deployment, Agent-Bridge writes, BioCortex runtime
influence, or a scientific claim.

## Verification

Run:

```bash
./scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh
```

A direct source commit must finish with
`BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_ARTIFACT_DEPENDENCY_GRAPH`; a later
unchanged descendant may finish with the corresponding `VALID_INTEGRATED`
marker.
