# BioCortex × Agent-Bridge Track B identity-composition pack

Date: 2026-07-14

Frozen integrated baseline: `c8e070de0de2abca764c5060b5fba91a64b6f189`

Decision: `SOURCE_IDENTITY_COMPOSITION_IMPLEMENTED_NOT_LIVE_BOUND`

## Result first

The next three public nodes unlocked by the Track B dependency graph now have
source implementations: an exact-byte blind-map bijection validator, a
provider-neutral populated-review schema, and a private truth-manifest schema.
The packet also carries one synthetic composition joined across every artifact
byte stream actually present in the fixture, a strict purpose checker, a fixed
deterministic result, and a descendant-compatible source gate.

This is still source preparation, not a live trial stage.  The map program
returns `VALIDATION_ONLY_NOT_STAGE_RECEIPT`; it explicitly reports no O_EXCL
receipt proof, no stage custody proof, no post-generation gate satisfaction,
and no review, unblind, or scoring authority.  The live ledger and admission
packet remain unchanged.  No private runtime artifact was emitted and no side
effect was unlocked.

## Exact source artifacts

| Binding path | Repository artifact | SHA-256 | Grain |
|---|---|---|---|
| `review_and_blinding.map_bijection_checker_sha256` | `scripts/eval/biocortex_ab_track_b_map_bijection_v0.py` | `45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2` | one trial/private map validation |
| `review_and_blinding.review_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json` | `2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422` | one complete `trial × reviewer_slot` review object |
| `truth_inputs.truth_manifest_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json` | `520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6` | one trial/private truth-authority manifest |

All three remain graph nodes with `binding_satisfied=false`.  Their hashes in
this source manifest are not writes to the immutable live ledger.

## Map identity validation

The raw-files mode consumes ten files: contract, eligible frame, blind map,
sampling receipt, selected cases, private condition roster, capture,
generation, blind packet, and the exact 32-byte seed.  It computes nine map
commitments from the supplied bytes and joins the tenth identity,
`trial_id`, across all six parsed protocol artifacts.  It does not trust
caller-asserted contract, frame, capture, generation, packet, roster, selected
case, sampling, or seed hashes.

The validator additionally proves:

- selected-case order is identical across sampling, selected, map,
  generation and blind packet;
- the case × condition product is complete, with globally unique answer IDs;
- condition and answer IDs equal the fixed HMAC derivations;
- generation invocation order and per-case blind order equal independent HMAC
  ranks, with rank and truncated-ID collisions rejected;
- blind answer bytes and hashes are exactly the generated answer bytes;
- the entire reviewer-visible blind packet contains no direct condition key,
  condition ID or seed disclosure in raw/case-folded text, contiguous or
  separated hex, base32, standard base64 or URL-safe base64 form;
- sampling receipt creation precedes `first_condition_output_at_utc`, which
  does not follow blind-map creation;
- local and global case, condition, answer, text-byte, artifact-byte and input
  product caps hold.

Synthetic object inputs are explicitly labelled `synthetic_request` or
`synthetic_fixture`; only raw-files mode refers to external exact bytes.  All
modes still return a validation result, never a stage receipt.  The result
contains hashes and counts but no seed, condition mapping, answer ID,
condition ID, raw map, or private roster.

The object API rejects `input_mode=raw_files`; that label is reserved for the
ten-file CLI path so a reconstructed object cannot masquerade as validation of
external bytes.

## Review semantics

The review schema records one complete blind reviewer slot.  Every answer row
always contains response mode, abstention assessment, currentness, usefulness,
claim scores, matched registered forbidden handles/count, and a separate count
of unmatched unsupported assertions.

The split is intentional:

- `matched_forbidden_assertion_*` counts unique hits against assertions
  pre-registered in the truth manifest;
- `unmatched_unsupported_assertion_count` counts only new unsupported
  assertions absent from that registry, avoiding double counting;
- the matched count must equal the number of unique handles;
- expected/observed `answer/answer` maps to `not_required`, expected/observed
  `abstain/abstain` maps to `pass`, and either response-mode mismatch maps to
  `fail` so a reviewer can record an incorrect answer or abstention;
- a correct no-assertion abstention has vacuous `currentness=pass`; uncertain
  currentness cannot pass the later strict case gate.

This object is a review validator, not the strict-success gate.  A populated
review with `abstention_assessment=fail` is valid evidence of failure; the
later strict-case algorithm decides whether that evidence passes admission.

There is no preferred-answer, tie, note, timestamp, provider/model identity,
free-form self-attestation or provenance claim.  Raw response bytes and their
projection belong to the later review receipt/provenance chain, not this
populated-review object.  The schema itself cannot authorize execution,
unblinding or scoring.

## Truth-manifest semantics

Truth is represented at assertion value level rather than by splitting a
referent leaf into artificial “required” and “forbidden” identities.  A claim
rubric embeds the exact opaque `(claim, referent, predicate)` leaf once, then
binds required `ast_*` assertions, forbidden `ast_*` assertions with reason,
and authority/currentness/evidence digests.  This permits one current required
assertion and one stale forbidden assertion for the same claim.

The composition checker requires:

- claim ↔ `(referent, predicate)` bijection, while allowing one referent to
  carry multiple predicates;
- global required/forbidden assertion disjointness and keyed uniqueness;
- `score` rubrics to contain required assertions;
- `context_only` rubrics to contain no required assertion and at least one
  forbidden assertion;
- answer cases to have score rubrics and abstention cases to have none;
- at most 64 registered forbidden assertions per case;
- `truth_as_of <= knowledge_cutoff <= truth_created < first_output`;
- exact selected-case, contract, trial, referent-schema, blind-packet and
  truth-manifest hash joins.

The boundary fields say sealed-snapshot and request-scoped opaque-handle
bindings are *required*, not verified.  Real verification remains the job of
a future custody-bound truth-manifest checker.  No raw source key, raw value,
raw claim/referent/predicate ID, or authority tier appears in this manifest.

## Resolved and unresolved digest identities

The composition resolves three truth-root digests against bytes present here:
`contract_sha256`, `selected_case_manifest_sha256` and
`referent_schema_sha256`.  Each review also binds the exact truth-manifest and
blind-packet bytes, while `review_instruction_sha256` is checked only for
cross-review equality.

Eleven truth-root digests are format-checked but cannot be byte-resolved by this
packet because their private/upstream artifacts are absent:
`claim_authority_policy_sha256`, `custody_receipt_sha256`,
`gold_evidence_manifest_sha256`, `opaque_handle_profile_sha256`,
`prepared_input_sha256`, `private_handle_map_sha256`,
`projection_envelope_sha256`, `projection_interface_schema_sha256`,
`request_nonce_commitment_sha256`, `sealed_snapshot_sha256` and
`snapshot_producer_identity_sha256`.  Review-instruction bytes are likewise
absent.  These fields demonstrate schema/composition shape, not verified
provenance or custody.

## Weighting and strict decision rule

There is deliberately no claim weight.  A later strict case passes only when
every score rubric receives `2`; the case sampling weight is then applied once
downstream.  Adding claim weights here would introduce an unfrozen owner
policy and could apply prevalence weighting twice.

Review preference is also absent.  Track B currently freezes claim accuracy,
currentness, abstention, unsupported/stale assertions and usefulness, not a
pairwise preference policy.

## Composition integrity and resource shape

JSON Schema `uniqueItems` compares complete objects; it cannot express keyed
uniqueness or dynamic joins.  The purpose checker therefore separately rejects
duplicate case, answer, claim, referent/predicate-pair and assertion identities;
case/order/cartesian drift; claim-score omissions or extras; required/forbidden
overlap; unknown matched handles; count/handle disagreement; response-mode and
abstention contradictions; private condition tokens in the synthetic blind
packet; time reversal; and every locally resolvable root-hash mismatch.  The
format-only digest identities listed above remain explicitly outside that
claim.

The manifest fixes global caps in addition to local schema bounds: 4,096
cases, 64 conditions, 262,144 answers, 1,048,576 claim scores, 1,048,576 truth
assertions, 64 forbidden assertions per case, 64 matched forbidden handles per
answer, 16 MiB answer bytes, 32 MiB per artifact and 64 MiB total map input.
This prevents individually valid local arrays from composing into an
unbounded product.

The synthetic fixture has two cases, two private conditions, four answers,
two claim rubrics, three value assertions and one reviewer object.  Its blind
answer text is condition-neutral.  It demonstrates a current-required plus
stale-forbidden claim, a correct abstention, same-referent/different-predicate
identity, exact byte hashes, deterministic HMAC order, and the complete join
among the truth, review and map objects present in the fixture.  It contains no
real source data and grants no real-run authority.

## Schema and source hardening

The two Draft 2020-12 schemas use a deliberately restricted local subset.
Every schema node must be exactly one of a local `$ref`, a scalar `const`, or a
typed node; the no-op `{}` form is rejected.  Objects are closed and require
all declared fields.  Arrays, strings and integers are finite.  Unknown
keywords, remote/relative/encoded/unresolved references, reference siblings,
cycles, unused definitions, duplicate JSON keys, non-finite constants,
noncanonical JSON and invalid UTF-8 are rejected without network access or an
ambient schema library.

The built-in suite rejects 199 mutations with the exact expected error code:
8 JSON/canonical-byte mutations, 33 schema mutations, 65 map mutations, 81
composition-fixture mutations and 12 source/manifest mutations.  Two additional
positive controls prove that both response-mode mismatch directions remain
recordable with `abstention_assessment=fail`.  The suite covers schema grammar,
canonical bytes, HMAC derivation/order, artifact hashes, dynamic joins,
abstention/currentness, private-token encoding leakage, time order, resource
products, source catalog drift and authority laundering.

## Data-quality assessment

The acceptance grain is explicit for all three artifacts and every synthetic
row.  Completeness is exact set/order equality rather than matching counts.
Uniqueness is checked at case, condition, answer, reviewer, claim-pair and
assertion-handle grain.  Referential integrity reaches from truth rubric to
review score to blind answer and through all ten map identities.  Timeliness
uses an explicit as-of, cutoff, truth creation, first output and map creation
chain.  Validity covers canonical bytes, locally resolvable exact hashes,
restricted schema grammar and resource products.

These controls are why the packet does not mistake a locally valid JSON object
for trustworthy analytical evidence.  Schema acceptance is only the first
layer; purpose-level composition and source identity are mandatory before the
result is safe to cite even as synthetic mechanism evidence.

## Remaining structural blockers

Five tranche-local structural blockers remain explicit; this is not an
exhaustive live-admission inventory:

1. the ledger declares a map-bijection receipt obligation but has no binding
   field for its hash;
2. the ledger has no scalar knowledge-cutoff field for truth;
3. the ledger has no truth-manifest-checker binding;
4. temporal evidence adapter S3 remains `BLOCKED_FAIL_CLOSED`;
5. committed source artifacts are not runtime instances.

The live ledger independently retains three additional fieldless
`PRE_UNBLIND` obligations that this tranche does not resolve:
`both_command_request_raw_response_and_receipt_chains`,
`both_complete_review_objects`, and
`contract_scoped_o_excl_score_claim`.  They remain custodian-private blockers
even after the five local items above are addressed.

The map result therefore does not satisfy the post-generation gate.  A future
custodian-owned O_EXCL writer and custody receipt must be represented in a new
immutable contract before a real blind reviewer can be invoked.

## Derived next frontier

Treating the foundational four schemas and these three source artifacts as
completed authoring nodes derives exactly five independent-public candidates:

1. `reference_condition.context_builder_sha256`
2. `review_and_blinding.review_receipt_schema_sha256`
3. `sampling.sampling_seed_derivation_sha256`
4. `sampling.sampling_selection_algorithm_sha256`
5. `truth_inputs.strict_case_algorithm_sha256`

This is an authoring frontier, not an execution authorization.  The next safe
unit should stay small; the truth strict-case algorithm and review receipt are
natural composition successors, while reference context and the two sampling
algorithms remain separate review units.

## Verification

From a clean committed source or unchanged descendant:

```bash
./scripts/check-biocortex-ab-track-b-identity-composition-pack.sh
```

The immutable source commit must print
`BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_IDENTITY_COMPOSITION_PACK`; an unchanged
descendant prints `VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_IDENTITY_COMPOSITION_PACK`.
The gate also reruns the artifact-dependency graph and foundational-schema
gates, whose executable bytes are pinned respectively to
`20e0b36d583ad729b992a423834dbb7c05245c3689a5887e53fb04103222b001`
and `17e9c53917139b6555e1546ab8ae675f85075fc09141d5c0033c1734ae6242e5`.
It distinguishes 16 purpose-checker evidence inputs from six prerequisite-only
inputs, reconstructs an immutable HEAD snapshot, runs the purpose checker and
its adversarial suite twice, and compares the normal result byte-for-byte with
the fixed expected file.

Neither marker authorizes private reads, capture, generation, review,
unblinding, scoring, deployment, Agent-Bridge writes, BioCortex runtime
influence, or a scientific/performance claim.
