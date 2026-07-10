# SpecFormer Memory Shadow Probe: NO-GO Checkpoint

Date: 2026-07-09
Status: `NO-GO` for runtime adoption; experiment lane closed; fixtures sanitized

## Decision

Preserve the completed read-only, offline shadow experiment that tested whether
graph-frequency features from the Agent-Bridge memory graph were worth
promoting into a retrieval side signal.

This is inspired by SpecFormer, but it is deliberately not a full SpecFormer
implementation. The experiment exposed the graph spectrum as a bounded
diagnostic, then evaluated it as both a direct side signal and a two-stage
candidate generator. Both runtime-admission shapes failed.

Final decision:

- do not add a SpecFormer or spectral-graph runtime adapter;
- do not change default retrieval ordering;
- do not train a SpecFormer-like filter from this signal;
- do not expand this experiment lane from the current evidence;
- retain the code, fixed corpora, frozen side signal, and negative result as a
  reproducible checkpoint.
- keep persisted fixture identities opaque; never check in raw AB memory keys or
  a reverse mapping.

Reopening requires materially new independent evidence, a new preregistered
gate, and an explicit runtime review. Parameter sweeps or a larger corpus alone
do not meet that bar.

## Boundary

The probe must:

- open `state.db` with `SqliteStore::open_read_only`;
- avoid memory writes, edge writes, embedding rewrites, and schema migration;
- avoid `memory_search` reranking and runtime retrieval mutation;
- report `runtime_adapter_approved=false`;
- emit only typed SHA-256 opaque IDs in reports and fixtures;
- keep the sampled graph bounded with `SPECFORMER_SHADOW_MAX_NODES`.

The probe must not:

- register an `EmbeddingBackend`;
- call BioCortex runtime surfaces;
- claim that spectral proximity improves retrieval until a fixed corpus gate
  measures it;
- run in the live retrieval path.

## Implementation

The first probe is checked in at:

`crates/bridge/examples/specformer_memory_shadow.rs`

It performs four steps:

1. Load a bounded set of active memories by importance, skipping volatile kinds
   by default: `skill`, `work_memory`, `session_handoff`, and `snapshot`.
2. Build an undirected weighted graph from existing memory edges, combining
   parallel edge types by max weight.
3. Compute the normalized graph Laplacian and a small low-frequency basis using
   a dense Jacobi eigensolver. This is acceptable for the bounded offline
   sample, not for an online hot path.
4. Emit either a markdown/JSON graph diagnostic or JSONL side-signal preview
   rows:

```json
{"query_id":"abmkey:sha256:<64-hex>","candidate_key":"abmkey:sha256:<64-hex>","score":0.73}
```

The side-signal score is spectral proximity only. It is bounded to `[0, 1]` so
it can later be adapted to the existing retrieval gate shape, which accepts
bounded benchmark-only side scores.

### Opaque identifier contract

Every persisted memory identity uses:

`abmkey:sha256:SHA256("agent-bridge/specformer/memory-key/v1" || NUL || raw_key)`

The prefix and hash domain make the identifier typed and versioned. Gates build
an ephemeral `opaque_id -> MemoryRecord` index from the read-only DB, fail closed
on collisions or missing IDs, and discard the index at process exit. No reverse
mapping is stored.

Starter queries contain no memory keys and remain byte-identical under
`query_literal`. Expanded queries use `query_template`; every raw key occurrence
is replaced by an opaque token and restored only in process before embedding.
Equal-score side rows retain fixture order, while semantic ties retain the raw
key sort order only inside the process. These two rules keep sanitization from
changing the measured ranks.

## SpecFormer Mapping

SpecFormer converts Laplacian eigenvalues into spectral tokens and learns a
set-to-set spectral filter. This probe only implements the non-trainable
measurement substrate:

- `normalized Laplacian` = graph-frequency operator;
- low non-zero eigenvalues/eigenvectors = coarse graph-frequency coordinates;
- spectral proximity = candidate side signal for later gate evaluation.

The intentionally missing piece is the Transformer spectral filter. That stays
out until the non-trainable spectrum shows measurable value.

## Runbook

Markdown diagnostics:

```bash
cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow
```

JSON report:

```bash
SPECFORMER_SHADOW_FORMAT=json \
  cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow
```

JSONL side-signal preview for explicit seed memories:

```bash
SEED="$(jq -r '.query_id' crates/bridge/tests/fixtures/specformer_memory_shadow_gate_corpus.jsonl | head -1)"
SPECFORMER_SHADOW_FORMAT=jsonl \
SPECFORMER_SHADOW_SEEDS="$SEED" \
  cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow
```

Useful knobs:

- `AGENT_BRIDGE_DB`: state DB path; defaults to `ab_store::default_db_path`.
- `SPECFORMER_SHADOW_MAX_NODES`: bounded graph size; default `160`, max `500`.
- `SPECFORMER_SHADOW_K`: non-zero low-frequency dimensions; default `8`.
- `SPECFORMER_SHADOW_TOP_M`: side-signal candidates per seed; default `8`.
- `SPECFORMER_SHADOW_GRAPH_MODE`: `edge-only`, `related-hybrid`, or
  `related-only`; default `edge-only`.
- `SPECFORMER_SHADOW_RELATED_WEIGHT`: weight for `related_keys` edges when a
  related graph mode is enabled; default `1.5`, clamped to `[0, 2]`.
- `SPECFORMER_SHADOW_SKIP_KINDS`: comma-separated kind filter.

## Historical Admission Path

This probe was not a runtime admission. The completed gate sequence was:

1. Build a fixed seed-key corpus where the expected documents are known.
2. Generate spectral JSONL side signals from this probe.
3. Blend them in a copy of the existing retrieval-gate evaluation shape.
4. Require zero expected-document regressions and a pre-registered MRR lift.

The 36-case expanded gate failed this contract, and the subsequent two-stage
semantic rerank gate also failed. The admission path is therefore closed for
this experiment shape.

## Starter Gate

The first fixed corpus is checked in at:

`crates/bridge/tests/fixtures/specformer_memory_shadow_gate_corpus.jsonl`

It preserves relationships from a prior live spectral run, but stores identities
only as opaque IDs. Candidate content is loaded from `state.db` at evaluation
time, so the fixture stays compact and tests the actual memory rows.

Fixture sha256:

`26adb360e43cc76020ee59905cd8038efa867fb31817b0a97b020bcbd0bc4b67`

Generate a side-signal file:

```bash
CORPUS=crates/bridge/tests/fixtures/specformer_memory_shadow_gate_corpus.jsonl
SEEDS="$(jq -r '.query_id' "$CORPUS" | paste -sd, -)"
SPECFORMER_SHADOW_FORMAT=jsonl \
SPECFORMER_SHADOW_MAX_NODES=350 \
SPECFORMER_SHADOW_TOP_M=20 \
SPECFORMER_SHADOW_SEEDS="$SEEDS" \
  target/debug/examples/specformer_memory_shadow > /tmp/specformer_side.jsonl
```

Run the gate:

```bash
SPECFORMER_SHADOW_SIDE_SIGNAL=/tmp/specformer_side.jsonl \
  cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow_gate
```

The starter gate requires:

- at least 5 cases;
- side-signal coverage at least 80 percent;
- zero expected-document rank regressions;
- MRR lift at least +0.03.

Passing this starter gate still did not authorize runtime retrieval influence.
It only justified the completed expansion to a 30+ case corpus.

Current starter result:

| policy | coverage | regressions | baseline MRR | blended MRR | delta | status |
|---|---:|---:|---:|---:|---:|---|
| `conservative` | 1.00 | 0 | 0.69444 | 0.69444 | +0.00000 | `side_signal_fails_starter_gate` |
| `candidate-strong` | 1.00 | 0 | 0.69444 | 0.69444 | +0.00000 | `side_signal_fails_starter_gate` |

Candidate-generation-only result from the same side-signal file:

| candidate_k | expected recall | side MRR | status |
|---:|---:|---:|---|
| 5 | 1.00 | 0.44444 | `passes_candidate_generation_starter_gate` |
| 20 | 1.00 | 0.44444 | `passes_candidate_generation_starter_gate` |

Interpretation: the raw spectral side signal is not destructive on the starter
corpus, but it does not improve expected-document rank. It does pull every
expected key into the top-5 spectral candidate set. Low-frequency proximity is
therefore too coarse for ranking authority, but was provisionally promising as
a candidate-generation / recall-expansion signal. That provisional result was
subsequently rejected by the 36-case and two-stage gates below.

Implementation note: `memory_get` is not read-only in practice because it bumps
access metadata. The gate therefore uses `list_memories` to build a read-only
snapshot and filters candidate keys in memory.

## Expanded Graph-Label Gate

The 30+ case expansion is checked in at:

`crates/bridge/tests/fixtures/specformer_memory_shadow_gate_graph_label_corpus.jsonl`

It was generated by:

`crates/bridge/examples/specformer_memory_shadow_corpus.rs`

The corpus generator is also read-only. It samples active memory rows, prefers
explicit `related_keys` labels, and falls back to existing memory graph edges
inside the sampled graph. The checked-in fixture has 36 cases.

Fixture sha256:

`aab2342fd531f27200a14073a4edce126d62c823fefc05a64e0c064491d00006`

Generate side-signal rows for this corpus:

```bash
CORPUS=crates/bridge/tests/fixtures/specformer_memory_shadow_gate_graph_label_corpus.jsonl
SEEDS="$(jq -r '.query_id' "$CORPUS" | paste -sd, -)"
SPECFORMER_SHADOW_FORMAT=jsonl \
SPECFORMER_SHADOW_MAX_NODES=350 \
SPECFORMER_SHADOW_TOP_M=20 \
SPECFORMER_SHADOW_SEEDS="$SEEDS" \
  target/debug/examples/specformer_memory_shadow > /tmp/specformer_graph_label_side.jsonl
```

Run the expanded gate:

```bash
SPECFORMER_SHADOW_GATE_CORPUS="$CORPUS" \
SPECFORMER_SHADOW_SIDE_SIGNAL=/tmp/specformer_graph_label_side.jsonl \
SPECFORMER_SHADOW_CANDIDATE_K=20 \
  target/debug/examples/specformer_memory_shadow_gate
```

Current expanded result after the graph-construction sweep:

Graph summaries with `SPECFORMER_SHADOW_MAX_NODES=350`:

| graph mode | edges | memory edges | related edges | hybrid edges | components | largest component | isolates | spectral gap proxy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `edge-only` | 862 | 862 | 0 | 0 | 41 | 293 | 34 | 0.000003 |
| `related-hybrid` | 1145 | 862 | 583 | 300 | 22 | 327 | 19 | 0.001930 |
| `related-only` | 583 | 0 | 583 | 0 | 60 | 266 | 50 | 0.000005 |

Gate summaries use the conservative `alpha=0.20` policy unless noted:

| graph mode | top_m | candidate_k | coverage | regressions | baseline MRR | blended MRR | delta | candidate recall | side MRR | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `edge-only` | 20 | 20 | 0.45556 | 4 | 0.51065 | 0.50926 | -0.00139 | 0.55556 | 0.17682 | `side_signal_fails_starter_gate` |
| `related-hybrid` | 20 | 20 | 0.57778 | 6 | 0.51065 | 0.47824 | -0.03241 | 0.63889 | 0.21754 | `side_signal_fails_starter_gate` |
| `related-only` | 20 | 20 | 0.59444 | 7 | 0.51065 | 0.48287 | -0.02778 | 0.75000 | 0.27637 | `side_signal_fails_starter_gate` |
| `related-hybrid` | 50 | 50 | 0.70556 | 6 | 0.51065 | 0.49769 | -0.01296 | 0.75000 | 0.22154 | `side_signal_fails_starter_gate` |
| `related-only` | 50 | 50 | 0.67222 | 6 | 0.51065 | 0.47269 | -0.03796 | 0.80556 | 0.30944 | `side_signal_fails_starter_gate` |

Interpretation: the starter 6-case candidate-generation result was optimistic.
Adding explicit `related_keys` edges improves recall, which proves the graph
construction was part of the problem. It still does not make low-frequency
spectral proximity admissible: top-20 stays below the 0.80 candidate-recall
gate, and every blend causes expected-document rank regressions. `related-only`
can pass candidate-generation recall as a very wide top-50 pool, but that is not
a ranking signal and is too broad to promote without a downstream rerank gate.

Implementation note: the corpus fixture is fixed, but the side-signal graph is
sampled from live `state.db` by importance. Exact graph counts can drift as new
memories are saved. The decision above is based on the stable repeated pattern:
related edges improve recall, but spectral proximity still fails ranking.

## Two-Stage Semantic Rerank Gate

The two-stage expansion gate is checked in at:

`crates/bridge/examples/specformer_memory_two_stage_gate.rs`

The default side-signal input is now frozen at:

`crates/bridge/tests/fixtures/specformer_memory_shadow_related_only_top50_side_signal.jsonl`

Fixture facts:

- graph mode: `related-only`;
- graph sample size: `SPECFORMER_SHADOW_MAX_NODES=350`;
- side-signal width: `SPECFORMER_SHADOW_TOP_M=50`;
- rows: 1800;
- sha256:
  `6a8ae040dd7405e05974ca58fa7e2e58e2e93022065d0ddc0983f3e0bf31e077`.

This freezes the graph candidate stage. Candidate contents are still loaded
read-only from `state.db`, matching the opaque-id gate convention.

Default replay:

```bash
cargo run -q -p ab-bridge --no-default-features --example specformer_memory_two_stage_gate
```

It evaluates the next admissible shape:

1. Use the graph side signal only as a candidate generator.
2. Ignore spectral scores for ranking.
3. Rerank the graph-expanded candidate pool with the active embedding backend.
4. Also rerank `fixed corpus candidates ∪ graph candidates` to detect whether
   adding the wide pool harms known-good candidate sets.

Default fixed-fixture results with `SPECFORMER_TWO_STAGE_CANDIDATE_K=50` and
`SPECFORMER_TWO_STAGE_RERANK_K=5`:

| graph mode | graph recall@50 | missing expected | graph MRR | expansion semantic recall@5 | expansion semantic MRR | union recall@5 | union MRR | union regressions | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `related-only` frozen top-50 | 0.80556 | 7 | 0.30944 | 0.44444 | 0.27489 | 0.50000 | 0.32162 | 26 | `two_stage_fails_shadow_gate` |

Fixed 5-candidate semantic baseline on the same 36 cases is MRR `0.51065`,
recall@1 `0.30556`, and recall@5 `1.00000`.

Two-stage interpretation: the frozen `related-only top50` fixture barely passes
the graph-candidate recall threshold, but the semantic reranker recovers only
44.4 percent of expected keys in the top 5. The union rerank is worse: adding
graph candidates to the fixed candidate set causes 26 expected-document rank
regressions. This rules out the simple two-stage design as a runtime candidate.

Final decision: `NO-GO`. Do not promote the raw spectral side signal, do not add
a runtime adapter, and do not train a SpecFormer-like filter from this signal as
currently shaped. No further experiment is scheduled. The frozen fixture and
this report are retained as negative evidence so the rejected design is not
re-proposed without materially new evidence.

## Non-Claim

This does not prove that every spectral graph feature is useless. It does show
that the measured raw low-frequency proximity and the measured two-stage
expansion shape fail the preregistered runtime gates on this checkpoint. The
result authorizes no runtime influence.

Sanitization is scoped to this SpecFormer checkpoint and prevents these
artifacts from adding raw AB memory keys. It does not claim that unrelated,
pre-existing repository fixtures or reports contain no memory-key references.
The deterministic hashes are one-way pseudonyms, not salted anonymization; they
remove semantic key text but are not intended to resist enumeration by someone
who already possesses a candidate raw-key set.
