# BioCortex Track B context and sampling determinism pack

## Technical summary

The next three independent-public Track B source nodes are now implemented as
three separate deterministic Python artifacts:

1. a case-grain reference-context projection builder;
2. a public sampling-seed derivation algorithm; and
3. a stratified full-width HMAC selection algorithm.

The source packet is deliberately non-admitting. It validates synthetic known
answers and derives exactly one next public authoring frontier,
`sampling.sampling_receipt_writer_sha256`, but it does not bind a runtime
configuration, eligible frame, entropy custody chain, sampling receipt, reviewer
packet, score, or unblinding authority. All side effects remain `NONE`.

The normal diagnostic has 68 exact rows. The current self-test rejects 62
directed mutations and accepts seven positive sensitivity, compatibility, or normalization
controls. These numbers describe source validation coverage, not statistical
evidence and not a real-run sample.

## Three source nodes close the intended public frontier

The frozen dependency graph classified all three targets as
`INDEPENDENT_PUBLIC`, with no local or external source-node dependencies,
`PRE_OUTPUT_ADMISSION` timing, `EXACT_COMMITTED_ARTIFACT_ONLY` fill rules, and
`unlocks_side_effect=false`.

| Binding path | Source artifact | Exact source behavior |
|---|---|---|
| `reference_condition.context_builder_sha256` | `scripts/eval/biocortex_ab_track_b_reference_context_builder_v0.py` | Projects one complete ranked reference page to exact compact UTF-8 bytes; no retrieval or runtime selection |
| `sampling.sampling_seed_derivation_sha256` | `scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py` | Derives one 32-byte seed by SHA-256 over the frozen five-part NUL-framed message |
| `sampling.sampling_selection_algorithm_sha256` | `scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py` | Orders each stratum by full HMAC-SHA-256, selects the first `n_h`, and reports exact rational probability/weight rows |

This table is used instead of a chart because the decision depends on exact
binding-to-file lookup and protocol semantics; a quantitative chart would hide
the byte-level relationship rather than clarify it.

Before this packet, nine of 13 independent-public graph nodes had source
artifacts. Treating only these three exact committed files as newly authored
raises that count to 12. Re-deriving the graph frontier produces exactly:

```text
sampling.sampling_receipt_writer_sha256
```

The dependency graph, live ledger, real-run admission packet, foundational
schemas, identity pack, and strict-review pack remain unchanged.

## Reference projection has one explicit case-page grain

The reference builder input grain is one opaque `case_id` times one complete,
ranked reference page. The page must have explicit, unique, contiguous ranks
`1..N`; input array order is not semantic. Memory keys must be unique. `skill`
rows and non-`active` rows are rejected.

For each admitted hit, the exact compact JSON field order matches the Rust
`MemorySearchReferenceHit` struct:

```text
rank, key, kind, content, tags, related_keys, scope,
created_at, updated_at, status, trigger_pattern, superseded_by
```

Tags and related keys are sorted by UTF-8 bytes and deduplicated. This is an
intentional normalization-equivalence rule inherited from S0, not a duplicate
rejection rule. Mutable read-side fields such as `access_count`,
`last_accessed_at`, `importance`, `score`, and `cosine` are absent from the
accepted field set. Inside that admitted profile, optional and list strings may
be empty and timestamps cover the full signed 64-bit Rust domain.

The algorithm first counts attacker-controlled UTF-8 text and rejects inputs
above 32 MiB before building normalization sets or JSON. It then computes the
exact compact-JSON UTF-8 size, including control-character escape expansion,
and rejects an over-budget page before materializing the serialized string. An
unpaired Unicode surrogate has a stable terminal error. The 16 MiB complete
context ceiling never truncates the tail because tail removal could hide a
recalled gold item.

The 16 MiB ceiling is an implementation safety maximum, not the owner-selected
per-case budget. The admission packet still leaves the real byte budget, token
budget, tokenizer, fixed clock, snapshot, binary, SQLite runtime, and effective
environment unset.

The synthetic multibyte vector produces 550 UTF-8 bytes and context SHA-256
`1c04feac310f4ba34bf2a09937607b3a4b9ce2f48c05dbe726576112fc366535`.
An independent empty-page vector freezes `[]` at two bytes and SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The public diagnostic exposes only case ID, hash, byte count, hit count, input
byte count, and false-boundary flags; it does not expose context content.

The checker binds both the existing S0 admission example and the actual Rust
implementation in `crates/store/src/lib.rs`. Independent cross-language vectors
covering control characters, U+2028/U+2029, emoji, empty optional/list values,
and signed timestamps produced byte-identical Rust/Python compact JSON. This is
accepted-domain projection compatibility, not proof that the Python source is a
live Rust runtime instance.

## Seed derivation freezes one unambiguous message

The seed source freezes this exact primitive:

```text
seed = SHA256(
  "agent-bridge/track-b/sample/v1" UTF-8
  || NUL || contract_sha256 ASCII
  || NUL || trial_id UTF-8
  || NUL || eligible_frame_sha256 ASCII
  || NUL || external_entropy_sha256 ASCII
)
```

All SHA-256 inputs must be 64 lowercase hexadecimal characters. `trial_id`
uses the frozen bounded label profile, which excludes NUL. Callers cannot choose
the primitive, domain, field order, separator, or encoding.

Seed derivation and case selection share the already frozen public sampling
domain. Their separation is provided by different primitives and different
message arity: plain SHA-256 over five fields for derivation versus keyed HMAC
over four fields for selection. This report does not claim that the two domain
strings differ.

The public result includes the domain and all five committed derivation inputs,
plus `sampling_seed_sha256`. Anyone can therefore reconstruct the derived seed
after the external entropy commitment is published. This is intentional:
`derived_seed_publicly_recomputable=true` and `seed_secrecy_claimed=false` are
tested protocol facts. The result does not redundantly serialize the 32 seed
bytes, and `SeedDerivation.__repr__` suppresses them as output hygiene only;
neither property is a confidentiality boundary.

The independent known-answer vector is:

| Input | Value |
|---|---|
| contract | `00` repeated 32 bytes |
| trial | `trial_v0` |
| eligible frame | `11` repeated 32 bytes |
| entropy digest | `22` repeated 32 bytes |
| derived seed | `687970671f77da52f4ebd4a23f4b4a1bc8805a39df666d784f514ee0c7104870` |
| public seed commitment | `400cadc7bd5b802c1762f55a04f69622dee191bc65f7018aef0b03e938570d1d` |

The pure function cannot establish that the external value was unavailable
before frame freeze, that no single party selected among candidate entropy
values, that the eligible frame was frozen with `O_EXCL`, or that derivation
preceded the first condition output. Those anti-shopping claims require later
custody and timing receipts; they do not depend on post-publication seed secrecy.

## Selection is deterministic without modulo bias

For every case in every stratum, the selection key is:

```text
HMAC-SHA-256(
  key = 32-byte sampling seed,
  message =
    "agent-bridge/track-b/sample/v1" UTF-8
    || NUL || eligible_frame_sha256 ASCII
    || NUL || stratum UTF-8
    || NUL || case_id UTF-8
)
```

The algorithm sorts full 256-bit digests within each stratum and selects the
first `n_h`. It performs no integer or modulo reduction. A digest collision is
terminal; it is not hidden by a secondary case-ID tie-break.

Selected rows are projected in opaque case-ID order, so the public-facing
selected manifest does not directly serialize HMAC rank. Reserve rows retain
canonical stratum and HMAC-rank order. Anyone with the published derivation
bindings and eligible-frame rows can still recompute every rank; no rank secrecy
is claimed. Selected and reserve sets must be disjoint and must partition the
supplied frame exactly.

For each selected case, the algorithm emits reduced rational inclusion
probability `n_h/N_h` and its reduced reciprocal weight `N_h/n_h`. The arrays
join selected cases one-to-one in the same case-ID order. The algorithm reports
but never applies weights; a later estimator may apply each weight exactly once
at case grain after strict reviewer conjunction.

The selection commitment is SHA-256 over the canonical complete result envelope
except the commitment field itself. It therefore covers:

- the sampling seed commitment;
- domain and message profile;
- eligible-frame commitment;
- selected and reserve projections;
- inclusion probabilities and weights;
- stratum population, sample, and reserve counts; and
- schema, status, invariance markers, and every false authority/boundary flag.

Changing a seed therefore changes the selection commitment even in the rare
case that it produces the same selected/reserve partition.

## Data-quality and adversarial checks

The validation dataset has three distinct grains:

| Surface | Intended key/grain | Integrity rule |
|---|---|---|
| Reference input | `case_id × rank` | Contiguous ranks, unique memory keys, complete-page projection |
| Eligible sampling frame | `case_id` with one stratum | Unique cases and exact allocation-stratum coverage |
| Sampling result | selected `case_id` | Probability and weight rows join selected rows exactly once and reciprocally |

The checker profiles completeness, uniqueness, validity, integrity, leakage,
and resource shape before interpreting any result. The current self-test covers:

- six canonical-JSON failures, including duplicate keys, NaN, BOM, invalid
  UTF-8, compact noncanonical bytes, and wrong root type;
- 16 context failures, including telemetry injection, bool confusion, rank/key duplication,
  rank gaps, excluded kind/status, item and input caps, invalid case/budget,
  unpaired surrogates, raw-input caps, and pre-serialization escaped-output overflow;
- six seed failures for unknown fields, schema, hash encodings, NUL injection,
  and entropy commitment format;
- 14 selection failures for unknown fields, schema/hash drift, type confusion, duplicate or
  malformed cases, allocation coverage/duplication/bounds, seed length, and
  forced full-width HMAC collision;
- seven fixture-boundary and known-answer mutations; and
- 13 manifest/binding/frontier/evidence/resource/obligation mutations, including
  removal of the bound Rust S0 implementation.

Seven positive controls prove that every seed input changes the derived seed,
that the selection commitment binds the seed, that duplicate/permuted
tag/related-key inputs normalize to the same S0 bytes, and that the accepted
empty-string/signed-timestamp domain remains aligned with Rust.

The public 68-row diagnostic is checked for absence of:

- directly serialized derived-seed bytes, while explicitly reporting that the
  seed is publicly recomputable;
- context content and memory keys;
- selected/reserve case IDs and case weights;
- opaque answer IDs; and
- condition IDs or condition mappings.

No scan is applied to arbitrary memory content, because historical content may
legitimately contain those strings. The guarantee is on protocol fields and
the public diagnostic surface.

## Exact source and verification artifacts

| Artifact | SHA-256 |
|---|---|
| Rust S0 implementation | `4e357d77d35d82c7fe6ac8de5b1870af7296cf10c72cf57ff684e49625a0638b` |
| Reference builder | `c37ac35cb349170b6830fb900de642bfc9572111b351bb031244c0485e282227` |
| Seed derivation | `4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f` |
| Sampling selection | `e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec` |
| Synthetic fixture | `5d31766048a9d5c6f61ee60c79dd00fba3ca9993017eb5c5fedb7d6bd31cb3ca` |
| Pack manifest | `06f54d4079e09d7728effd242d9dbf0e35f4d050e0d7a9f6a5fc9a8202b9445f` |
| Expected 68-row diagnostic | `5f3983ec8cfac3c740a8fc2fc7f1181d747854ddd514038302dfca753d25114f` |
| Self-test output | `c09a37aa1f87a88933cd34b6070d400d020d4939f367189698cedcdd97441e90` |

The shell gate additionally binds the exact nine-path all-add source commit to
frozen baseline `d4e4093d9b273bc36ed2fb4c373e15dcd8467a55`, requires the baseline to be
the source commit's sole raw parent, and requires an ordinary two-parent merge
of that exact source commit for descendant validation. It rejects replace refs,
grafts, shallow history, symlink or hard-link aliases, nondefault index flags,
mode drift, dirty trees, and worktree/index/HEAD/source-blob divergence.

The purpose checker executes from a read-only immutable Git-blob snapshot under
two `PYTHONHASHSEED` values. Both normal and self-test outputs must be
byte-identical; the normal output must match the checked-in TSV, and the
self-test output hash is fixed.

## Important limitations remain blockers, not caveats to waive

Two newly explicit interface gaps prevent a live claim even after these source
artifacts exist.

First, `contract_sha256` needs a non-circular preregistration-core definition.
If it names a final contract that itself contains the derived seed or sampling
receipt hash, seed derivation creates a hash cycle. No such non-circular digest
profile is currently bound.

Second, the frozen sampling-receipt schema binds the seed-entropy receipt and
seed-derivation algorithm, but does not contain `sampling_seed_sha256`. The
selection source commits to the seed, but the current public receipt shape
cannot yet prove that the same seed reached selection. The next receipt-writer
unit must not conceal this schema gap.

Other retained blockers include:

- no eligible-frame or strata-allocation manifest schemas;
- no frame `O_EXCL` or entropy-custody receipt;
- no owner-selected reference byte/token budgets or tokenizer;
- no runtime clock, snapshot, binary, environment, or context receipt;
- no reviewer roster, instruction, raw-response provenance, or truth-gate
  provenance; and
- no real runtime instance of any source artifact.

All 12 real-run admission blockers and all four post-generation/pre-unblind
stage obligations remain present. A source hash is not a live binding, and a
synthetic known-answer vector is not a real frame, entropy beacon, context, or
receipt.

## Recommended next step

The next safe public unit is the sampling-receipt writer, because its three
local source dependencies will then exist:

1. the already frozen sampling-receipt schema;
2. this seed-derivation algorithm; and
3. this sampling-selection algorithm.

That unit should create receipts with fail-closed no-overwrite behavior and
exact joins to frame, seed, selection, probability, and weight commitments. It
must either repair/version the missing seed-commitment field or stop with an
explicit blocker; it must also define a non-circular contract digest before any
runtime instance is admitted.

## Further questions

1. Should the receipt be versioned to include `sampling_seed_sha256`, or should
   a separate seed-binding receipt be mandatory and joined by the writer?
2. Which preregistration-core fields define the non-circular
   `contract_sha256` used by seed derivation?
3. Which owner packet will freeze the reference byte/token budgets, tokenizer,
   clock, snapshot, environment, and exact runtime wrapper?
4. Which schemas will own eligible-frame rows, stratum allocations, selected
   cases, and reserve order without turning the synthetic fixture into a
   production contract?

Until those questions are answered with exact committed artifacts and custody
evidence, the only valid decision remains:

```text
SOURCE_CONTEXT_AND_SAMPLING_DETERMINISM_IMPLEMENTED_NOT_LIVE_BOUND
```
