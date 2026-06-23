# Goal C U Follow-Up - Multilingual Embedder Upgrade Gate

Date: 2026-06-23

Scope: design / acceptance gate only. No production retrieval change, no vector
schema migration, no re-embed, no MCP surface change, and no memory writes.

Controlling board context:

- #3966 proposes a paper-grounded multilingual embedder upgrade lane for the
  Chinese hard misses in the standing `recall_eval` anchor.
- #3969 claims the isolated BGE-M3 vs e5 probe. This report does not duplicate
  that implementation lane; it defines how to accept or reject the broader
  embedder-upgrade direction.
- #3970 records the current U report boundary: `continuity-report` plus pinned
  `recall_eval` are the standing surfaces; embedder candidates are a separate
  memory-continuity input, not production authorization.

## Current Verified State

Repository state at the start of this report:

```text
HEAD = origin/master = github/master = daa090d
working tree clean
```

Local ONNX cache:

```text
~/.cache/agent-bridge/onnx-models/
└── multilingual-e5-small
```

Current production-compatible vector path:

- `crates/store/src/vector.rs` fixes `VECTOR_DIM = 384`.
- Built-in `AGENT_BRIDGE_ONNX_MODEL` aliases cover `all-MiniLM-L6-v2`,
  `multilingual-e5-small`, and `paraphrase-multilingual-MiniLM-L12-v2`.
- Local user-defined loading expects
  `$AGENT_BRIDGE_ONNX_MODEL_DIR/<model-name>/model.onnx` plus tokenizer/config
  files and uses `Pooling::Mean` for the currently supported e5/MiniLM-style
  models.
- Therefore new candidates are not a safe drop-in until their dimension,
  pooling, tokenizer, prompt/instruction, and output-normalization contracts are
  explicitly tested.

Current e5 CJK micro-pool measurement:

```bash
AGENT_BRIDGE_ONNX_MODEL=e5-small \
  cargo run -p ab-store --example cjk_embed_compare
```

Result:

```text
model ready after ~2000 ms
relevant@rank1: 5/6
mean_rel_cos=0.892
mean_margin=+0.022
miss: recall query ranked 3 behind embed/browser
```

Read:

- e5 is not useless on the tiny CJK pool, but margins are thin.
- The standing pinned `recall_eval` remains the real U gate:
  hard-tier `semantic` R@10 is still `0.125`, while FTS/hybrid hard R@10 are
  `0.375`.
- A candidate model must move the pinned hard-tier result, not only the toy CJK
  pool.

## Literature Corrections And Candidate Facts

The #3966 direction is accepted: Chinese / multilingual embedding replacement is
a plausible high-leverage recall lane. One factual correction matters:

- The multilingual E5 technical report does include `DuReader Retrieval 86k` in
  its supervised fine-tuning mixture. The sharper claim is not "E5 has no
  Chinese retrieval data"; it is "the local e5-small backend is weak for this
  Chinese-dominant memory corpus, and E5-small's Chinese MIRACL row is
  materially lower than stronger/larger alternatives." The same report lists
  `zh` MIRACL nDCG@10 as `45.9` for the smallest mE5 column.

Primary-source facts used for gate design:

| Candidate | Useful fact | Gate implication |
|---|---|---|
| `BAAI/bge-m3` | Hugging Face model card lists 1024-dim embeddings, sequence length 8192, multilingual dense/sparse/ColBERT-style retrieval support. | Strong candidate, but not a 384-dim drop-in. Treat as scratch/sidecar first or require vector schema migration design. |
| `Qwen/Qwen3-Embedding-0.6B` | Model card lists 0.6B parameters, 100+ languages, 32k context, and user-defined output dimensions from 32 to 1024. | Best no-schema-change candidate if local inference can reliably emit 384-dim vectors. |
| `EmbeddingGemma` | Google states 100+ languages, quantized on-device footprint under 200 MB RAM, and customizable output dimensions from 768 to 128 via Matryoshka. | Good lightweight candidate; only use 384 if the local implementation explicitly supports that truncation/output contract. |

Sources:

- E5 technical report: <https://arxiv.org/html/2402.05672v1>
- BGE-M3 model card: <https://huggingface.co/BAAI/bge-m3>
- Qwen3-Embedding-0.6B model card:
  <https://huggingface.co/Qwen/Qwen3-Embedding-0.6B>
- EmbeddingGemma announcement:
  <https://developers.googleblog.com/introducing-embeddinggemma/>
- EmbeddingGemma paper: <https://arxiv.org/abs/2509.20354>

## Acceptance Gate

### Phase 0 - Loader Feasibility

Before judging model quality, prove the harness is not producing invalid vectors:

- real model load confirmed, no hash fallback;
- correct pooling per model;
- correct query/document instruction or prefix contract;
- expected output dimension observed;
- vector norm and cosine distribution sanity-checked;
- model files and tokenizer provenance recorded.

Failure here rejects only the harness, not the model.

### Phase 1 - Read-Only CJK Micro-Pool

Allowed:

- isolated examples under `crates/store/examples/`;
- no `state.db` writes;
- no production `vector.rs` behavior change;
- side-by-side e5 vs candidate ranking over the same labeled CJK pool.

Minimum pass condition:

- candidate `relevant@rank1` strictly exceeds e5's current `5/6`, or equals it
  with a materially larger mean margin and no new obvious semantic confusion;
- the recall-query failure class should improve, because that is the current
  visible micro-pool miss;
- no "green" result is accepted if fallback, pooling mismatch, or instruction
  mismatch is detected.

This phase can only authorize a pinned snapshot experiment.

### Phase 2 - Pinned Snapshot Re-Embed

Allowed:

- copy or sidecar of
  `$HOME/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db`;
- original snapshot remains immutable and read-only;
- candidate vectors written only into scratch storage;
- existing pinned `recall_eval` corpus used unchanged.

Dimension rule:

- 384-dim candidates may use an existing-shape scratch copy if the backend
  contract is verified.
- 1024-dim candidates such as BGE-M3 must use a sidecar/scratch schema or wait
  for an explicit vector schema migration design. They must not be squeezed into
  the 384-dim production column.

Minimum pass condition:

- hard-tier `recall_eval` R@10 must beat the current `0.375` production-mode
  ceiling, not only semantic-only submetrics;
- Chinese hard misses #1 and #9 are the priority recovery targets; #2 remains
  partly tool-surface/candidate-visibility shaped, so model-only recovery is not
  required there;
- easy/moderate tiers must not regress enough to trade one continuity failure
  for another;
- report must show before/after ranks for all hard misses #1, #2, #8, #9, #14.

This phase can only authorize a migration review.

### Phase 3 - Production Migration Review

Production work remains NO-GO until this review exists.

Required review contents:

- vector schema and dimension strategy;
- re-embed plan for active memories plus stale/null backend rows;
- rollback path to the previous embedding backend and vectors;
- mixed-backend query semantics while migration is incomplete;
- live `memory_search` blast radius;
- graph/cosine-derived edge impact;
- runtime resource envelope on Mac and aio2;
- deploy/reconnect proof plan;
- acceptance owner sign-off.

## Recommendation

Proceed, but keep the lane split:

1. Let #3969 own the isolated BGE-M3 probe.
2. In parallel, prefer a 384-dim-capable candidate feasibility path for
   Qwen3-Embedding-0.6B or EmbeddingGemma, because either may avoid the first
   schema migration while still testing Chinese in-domain lift.
3. Do not change default `memory_search`, `vector.rs`, vector schema, graph
   logic, or MCP tool exposure until Phase 2 beats the pinned hard-tier gate.

Current status: `ACCEPTED-AS-RESEARCH-GATE`, `PRODUCTION-NO-GO`.
