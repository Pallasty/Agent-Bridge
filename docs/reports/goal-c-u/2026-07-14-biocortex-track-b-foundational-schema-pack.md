# BioCortex × Agent-Bridge Track B foundational schema pack

Date: 2026-07-14

Frozen baseline: `a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259`

Decision: `SOURCE_ARTIFACTS_IMPLEMENTED_NOT_LIVE_BOUND`

## Result first

The first four provider-neutral roots from the Track B artifact dependency
graph now have exact public schema bytes, a detached hash manifest, synthetic
positive controls, a purpose-built validator, a fixed receipt, and a
source-bound gate.  They are source artifacts only.  No old admission scalar
was changed from `UNSET_BLOCKS_REAL_RUN`, no live binding was satisfied, no
authority bit became true, and no side effect was unlocked.

The packet deliberately starts from the current integrated baseline, which
already includes temporal evidence substrate S2.  S2 remains a crate-internal
synthetic storage mechanism with no producer adapter, Bridge/MCP surface, real
capture authority, or BioCortex runtime influence.  This schema pack consumes
its boundary as evidence; it does not claim to close it.

## Exact artifacts

| Binding path | Repository artifact | SHA-256 | Instance grain |
|---|---|---|---|
| `review_and_blinding.map_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json` | `ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783` | one private, single-use trial map |
| `review_and_blinding.review_command_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json` | `40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5` | one reviewer-slot invocation record |
| `sampling.sampling_receipt_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json` | `9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd` | one trial sampling decision receipt |
| `truth_inputs.referent_schema_sha256` | `docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json` | `5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8` | one request-scoped opaque claim component |

Every artifact uses a deliberately restricted Draft 2020-12 subset.  Schema
files are canonical sorted pretty JSON with one final newline.  Duplicate
keys, NaN/Infinity, unknown schema keywords, open objects, remote or relative
references, unresolved references, reference cycles, reference siblings,
unused definitions, nullable unions, and unbounded arrays are rejected.  Only
exact `#/$defs/<name>` references are allowed; validation never fetches a
network resource and does not depend on an ambient `jsonschema` package.

## Frozen semantics

### Blind map

The map binds the ten identity fields already frozen by the admission
contract: trial, contract, sampling receipt, eligible frame, selected cases,
condition roster, capture, generation, blind packet, and the answer-blinding
seed commitment.  It stores only opaque `case_*`, `ans_*`, and `cond_*`
handles.  The checker requires globally unique answer handles, unique
conditions within each case, and the same complete condition set across all
cases.  It accepts only the private, single-use, no-pre-review-read and
no-unblinding boundary.

The schema contains no raw seed, answer, context, prompt, score, reviewer,
provider, model, credential, source key, or truth material.  A later
map-bijection checker must still prove the map against the exact selected-case
manifest, condition roster, generation, blind packet and private seed-derived
procedure.

### Review command

The command artifact freezes a provider-neutral direct-exec record rather
than a universal shell envelope.  It binds trial, contract, blind packet,
instruction, executor profile, working-directory manifest, stdin request and
reviewer slot.  `argv` is an ordered 2–32 item printable-ASCII array; a command
string, shell, control character or backslash escape is rejected.  Context
environment keys are exactly empty.  Non-leading empty argv items are allowed
because a frozen provider profile may require an empty value such as
`--tools ""`; the checker separately requires a non-empty executable at index
zero.

Its boundary fixes an empty ephemeral workspace, no project/repository/MCP/
tool/external-fact access, no inherited parent environment, no credentials,
no condition map, no postprocessing, zero retry, O_EXCL single-response sink,
and `authorizes_execution=false`.  A later roster/provenance checker must bind
the exact provider profile and real invocation; this schema cannot run one.

### Sampling receipt

Apart from its schema discriminator, the top level contains exactly the 18
required bindings frozen by the admission contract.  The two case-grain
arrays use reduced positive integer fractions.  The checker independently
requires equal case sets and order, one probability and one weight per case,
`0 < p <= 1`, `w >= 1`, and exact `p × w = 1`.  Floats and booleans are not
integers.  Answer-, condition-, reviewer- or claim-grain rows are rejected.

The fixed domain and message remain
`agent-bridge/track-b/sample/v1` and
`domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8`.
The receipt carries no raw frame, seed, entropy, condition or output.  Its
`receipt_precedes_first_condition_output=true` is a required assertion, not
proof of wall-clock order; a later O_EXCL writer and provenance checker must
prove frame receipt → entropy receipt → derivation → sampling receipt → first
condition output.

`seed_entropy_receipt_sha256` projects to the ledger path
`sampling.sampling_seed_entropy_receipt_sha256`.  The contract's
`frame_o_excl_receipt_sha256` has no separate ledger scalar and remains an
internal sampling-receipt commitment whose exact artifact and transaction
semantics must be defined by the later writer.

### Truth referent

The referent schema is a leaf component containing only `claim_handle`,
`referent_handle`, and `predicate_handle`, in disjoint opaque 128-bit hex
namespaces.  It intentionally omits a per-instance schema discriminator; the
enclosing truth manifest and `referent_schema_sha256` bind the version.

It cannot carry raw `referent_id`/`predicate_id`, memory/source/lineage/
evidence keys, values, aliases, timestamps, truth tiers, authority policies or
currentness.  The synthetic control proves that one referent may retain two
different predicates and claim handles without collapsing identity.  A later
truth manifest must bind the private handle profile, sealed snapshot,
producer identity, trial, knowledge cutoff, truth-as-of time and authority
policy before any real instance is meaningful.

## Cross-schema integrity

The synthetic quartet contains four schema classes and five valid instances
(two referent leaves).  The checker verifies:

- identical trial and contract bindings across map, command and receipt;
- exact hash binding from the map to canonical sampling-receipt bytes;
- equal eligible-frame and selected-case manifest hashes;
- equal blind-packet binding between map and command;
- map case order equal to the sampling receipt's case order;
- sampling schema hash equal to the exact committed schema bytes;
- sampling receipt created before the map, and the map no later than command;
- no answer or condition identity in command or sampling material;
- reviewer-slot identity does not collide with case, answer or condition
  identifiers, and truth handles do not collide with any packet identifier;
- byte-identical shared label, SHA-256 and UTC primitive definitions.

The built-in adversarial suite rejects 101 fixed mutations: 14 schema-policy,
77 instance/cross-schema and 10 manifest/source mutations.  Mutations cover
remote refs, open objects, missing required fields, map non-bijections, shell
or context access, all 18 receipt-field deletions, bool/float/range/reduction/
reciprocal errors, identity leakage, authority laundering, linked receipt
resealing, catalog drift and false admission.

## Data-quality assessment

The intended grain is explicit for every artifact and synthetic row.
Completeness is established by exact set equality with the graph summary's
four-node `recommended_first_pack` and all 18 sampling bindings, not by counts
alone.  Uniqueness is
checked at case, answer, condition, probability, weight and claim-pair grain.
Validity covers canonical bytes, bounded ASCII namespaces, exact hashes,
rational arithmetic and immutable safety constants.  Referential integrity is
checked across all four schemas and against nine frozen public evidence
inputs.  Timeliness is bound to the current S2 integration baseline instead of
silently reusing the older graph baseline.

The main remaining risks are correctly externalized: schemas cannot prove a
real seed derivation, O_EXCL write, selected/reserve disjointness, reviewer
roster, provider command profile, sealed snapshot, opaque-handle derivation,
authority join, or event time.  Those remain later artifact and live-evidence
responsibilities.

## Inherited gate status

The artifact-dependency graph gate remains valid on the S2 baseline.  The old
live-binding-ledger v0 checker reports seven matching and four drifted source
bindings because S2 additionally changed `Cargo.lock`.  This is the intended
stale-packet signal, not a defect to hide or repair in place: the old receipt
must remain immutable.  The S2 gate similarly describes its own exact
single-tranche HEAD and is not expected to admit an unrelated descendant
packet.  The new gate therefore uses the graph gate's descendant-compatible
source-object model.

## Non-authority boundary and next frontier

A successful check still reports:

```text
source_artifact_count=4
schema_validated_count=4
live_binding_satisfied_count=0
authority_true_count=0
real_run_admitted=false
side_effects_unlocked=NONE
```

With these four roots treated only as completed source artifacts, the graph
derives a six-node public frontier: reference context builder, map-bijection
checker, review schema, sampling seed derivation, sampling selection
algorithm, and truth-manifest schema.  The recommended next packet is the
three newly unlocked identity-composition artifacts: map-bijection checker,
review schema, and truth-manifest schema.  The reference wrapper and
cryptographic sampling algorithms can remain separate review units.

## Verification

Run from a clean source or unchanged descendant worktree:

```bash
./scripts/check-biocortex-ab-track-b-foundational-schema-pack.sh
```

The source commit must print
`BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_FOUNDATIONAL_SCHEMA_PACK`; an unchanged
descendant prints the corresponding `VALID_INTEGRATED` marker.  Neither marker
authorizes private reads, capture, generation, review, unblinding, scoring,
deployment, Agent-Bridge writes, BioCortex runtime influence, or a scientific
claim.
