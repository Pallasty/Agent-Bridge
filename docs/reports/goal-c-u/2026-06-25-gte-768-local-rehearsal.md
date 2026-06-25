# GTE 768 Local Asset And Scratch Rehearsal

Date: 2026-06-25

Host: ThinkBook Linux local AB checkout

Commit under test: `c942297 chore(memory): add GTE 768 preflight script`

Scope: local model asset staging, loader smoke, and scratch-copy reindex only.
This report does not authorize or perform a live store migration.

## Source Model

Chosen ONNX bundle:

- repository: `onnx-community/gte-multilingual-base`
- revision: `2edbf5e672aab465f9ed4c154a8b61791c082c69`
- source model: `Alibaba-NLP/gte-multilingual-base`
- local cache: `~/.cache/agent-bridge/onnx-models/gte-multilingual-base/`
- variant: full `onnx/model.onnx`

The original `Alibaba-NLP/gte-multilingual-base` repository does not contain an
ONNX file. The `onnx-community` repository supplies the ONNX bundle plus the
same tokenizer/config files needed by the current fastembed user-defined loader.

Downloaded local files:

```text
config.json                 1648 bytes
special_tokens_map.json      964 bytes
tokenizer.json          17082734 bytes
tokenizer_config.json       1149 bytes
model.onnx            1255502649 bytes
```

Manifest:

`~/.cache/agent-bridge/onnx-models/gte-multilingual-base/asset-manifest.txt`

## Loader Smoke

Command:

```bash
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
AB_GTE_SMOKE_TIMEOUT_SECS=240 \
cargo run -p ab-store --example gte_embed_smoke
```

Result:

```text
[gte-smoke] model=gte-multilingual-base
[gte-smoke] ready_after_ms=4000
[gte-smoke] dim=768
[gte-smoke] para_sim=0.767
[gte-smoke] unrelated_sim=0.368
[gte-smoke] gap=0.399
```

Read: the local ONNX path loads, does not stay in hash fallback, and emits
768-dim vectors.

## Safety Gate Check Against Live Store

Command:

```bash
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
AB_RECALL_EVAL_CONFIRM_SECS=20 \
cargo run -p ab-bridge --example recall_eval 1
```

Result:

```text
# semantic gate: backend=gte-multilingual-base query_dim=768
# stored_backend=unknown stored_dim=384 stored_rows=244
# reason=query_dim 768 does not match stored_dim 384
## semantic — SKIPPED
```

Read: the gate correctly refuses to compare 768-dim GTE query vectors with the
current 384-dim live store. This protects against false semantic evidence before
reindex.

## Scratch Copy Reindex

Snapshot source:

```bash
agent-bridge.real rescue-snapshot --canonical --json
```

Rescue output:

```text
recovery_dir=/home/pallasting/.cache/agent-bridge/recovery/2026-06-25T1148
state.db sha256=3e340b36fc0bf22893f7f22579b2fc5a2e7b830b8b7c3b6073090a6e50d802d5
state.db-wal sha256=efc3118f59bca5ec7f7e2cf5958039ed58544d10240f77177ed01145fd1b8189
state.db-shm sha256=f6efff622de3ad9d1547582ca6a95a273d72683500ab01954e4a097b2a01f781
```

Scratch target:

`~/.cache/agent-bridge/gte-rehearsal/2026-06-25T1148-full-gte/state.db`

Before reindex active distribution:

```text
active=492
<null>,              1536 bytes, 244 rows
all-MiniLM-L6-v2,    1536 bytes, 230 rows
<null>,              NULL,         9 rows
fnv1a-hash-384,      1536 bytes,   9 rows
```

Reindex command:

```bash
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-store --example reindex_to_active_model -- \
  ~/.cache/agent-bridge/gte-rehearsal/2026-06-25T1148-full-gte/state.db
```

Result:

```text
[reindex] model ready after ~3500 ms
[reindex] batch reindexed 492 (running total 492)
[reindex] batch reindexed 0 (running total 492)
[reindex] DONE - reindexed 492 rows onto gte-multilingual-base
```

After reindex active distribution:

```text
active=492
null_embeddings=0
gte-multilingual-base, 3072 bytes, 492 rows
```

Read: scratch reindex can convert all active rows to 768-dim GTE vectors.

## Recall Eval On Reindexed Copy

Command:

```bash
AB_BASELINE_DB=~/.cache/agent-bridge/gte-rehearsal/2026-06-25T1148-full-gte/state.db \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
AB_RECALL_EVAL_CONFIRM_SECS=30 \
cargo run -p ab-bridge --example recall_eval
```

Gate result:

```text
semantic: ENABLED (real model confirmed and query/store embeddings match)
# semantic gate: backend=gte-multilingual-base query_dim=768
# stored_backend=gte-multilingual-base stored_dim=768 stored_rows=492
# semantic probe: confirmed=true timeout_secs=30 attempts=5 dim=768
# para=0.758 unrel=0.360 gap=0.398
```

Main recall result:

```text
mode       R@1    R@5    R@10    MRR
fts       0.167  0.278  0.333  0.201
hybrid    0.167  0.278  0.333  0.201
semantic  0.000  0.000  0.000  0.000

hard-tier R@10: fts=0.125 fts+graph=0.125 hybrid=0.125 semantic=0.000
```

Eval-only scoped semantic rows moved, but not enough for the production gate:

```text
C raw/no-scope R@10=0.000 hardR@10=0.000 purity=0.094
A soft-scope   R@10=0.222 hardR@10=0.125 purity=1.000
B hard-filter  R@10=0.222 hardR@10=0.125 purity=1.000
```

Read: the 768 GTE technical path works, but the current local 492-row store does
not reproduce the production acceptance benefit. Default semantic remains a
miss on the held-out corpus. Production live cut-over remains `NO-GO`.

## Verdict

Status: `ASSET_AND_REINDEX_PATH_VERIFIED`, `RECALL_BENEFIT_NOT_REPRODUCED`,
`PRODUCTION_NO_GO`.

What is now true:

- local GTE ONNX assets are staged;
- Rust/fastembed can load them and emit 768-dim vectors;
- scratch-copy reindex rewrites all active rows to
  `embedding_backend='gte-multilingual-base'` and 3072-byte embeddings;
- recall_eval semantic gate correctly skips mixed 768-query / 384-store cases;
- recall_eval semantic gate enables on the reindexed 768 copy.

What is not true:

- live store has not been changed;
- live readers have not been relaunched with GTE env;
- GTE has not demonstrated a main recall_eval hard-tier lift on this local
  store;
- production cut-over is not approved.

## Next Gate

Do not proceed to live migration yet. The next executable slice should answer
one of these before owner approval:

1. Run the same GTE rehearsal on the canonical frozen Mac snapshot that produced
   the earlier positive #4016 evidence, if available on this node.
2. Investigate why default semantic remains zero while scoped semantic recovers
   some local rows: candidate visibility, score blending, scope filtering, or
   gold-row absence may dominate model quality.
3. Compare full ONNX against `model_fp16.onnx` or `model_int8.onnx` only after
   the full-model baseline is archived, so quantization does not hide a logic
   problem.
