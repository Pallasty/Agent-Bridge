# Thread #106 post-reconnect runtime check

Date: 2026-07-02
Author: codex/current-session
Scope: read-only post-MCP-reconnect status check for the gte-768 embedding RAM lane.

## Result

Thread #106 should remain open as a roadmap/status thread, not as an active
merge target. The current `master` already contains the useful Track B runtime
levers:

- `RemoteEmbedBackend` daemon to daemon-http embedding delegation.
- `scripts/deploy-gte-int8-embedding.sh` per-node deploy/rollback.
- `scripts/quantize_gte_embedding_int8.py` embedding-only INT8 model generator.
- `embedding_quant_shadow` read-only diagnostic.

No old parked branch should be merged automatically.

## Current Runtime Readout

`agent-bridge.real doctor --json` after MCP reconnect:

- `ok=true`
- `fails=0`
- `warns=0`
- `mcp_servers`: 7 current `agent-bridge.real`
- current tool surface: 142 tools

Processes:

| Process | PID | RSS |
| --- | ---: | ---: |
| `agent-bridge.real daemon` | 2595 | 12,240 KiB |
| `agent-bridge.real daemon-http --listen 0.0.0.0:7878` | 2596 | 555,572 KiB |
| `agent-bridge.real palace serve --port 7979` | 2599 | 9,824 KiB |

Health:

- `http://127.0.0.1:7878/healthz`: `ok`
- `http://127.0.0.1:7979/healthz`: `ok`

Filtered environment:

| Process | Relevant env |
| --- | --- |
| daemon | `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`; `AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models-int8`; `AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed` |
| daemon-http | `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`; `AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models-int8`; `AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed` |

`/embed` probe:

- backend: `gte-multilingual-base`
- dim: `768`

## Embedding Quant Shadow

Read-only MCP call:

```bash
embedding_quant_shadow({ "k": 10, "max_queries": 100, "threshold": 0.98 })
```

Key output:

- schema: `agent_bridge.embedding_quant_shadow.v0`
- read_only: `true`
- verdict: `attention`
- active f32 corpus: 696 rows, all 768d
- drift compression ratio: `3.979275`
- drift mean cosine: `0.999959`
- drift min cosine: `0.999918`
- G1 recall: pass, mean recall@10 `0.997414`
- G2 zero regressions: fail, 3 queries below threshold
- G3 footprint: pass
- G4 cosine: pass
- G5 query f32 invariant: pass
- G6 human review: fail, as expected for a shadow-only diagnostic
- persisted shadow coverage: `0.232759` (162/696 rows)
- stored-vs-f32 mean cosine: `0.998754`
- stored-vs-f32 min cosine: `0.804291`

Interpretation: the RAM-reduction runtime path remains healthy. The INT8 corpus
promotion path remains explicitly gated; `attention` does not imply current
runtime degradation, only that Phase C must not proceed without resolving the
zero-regression and human-review gates.

## Decision

No runtime action was taken:

- no service restart;
- no systemd drop-in change;
- no DB or embedding write;
- no reindex;
- no retrieval order change;
- no Phase C cutover.

Keep #106 open as a roadmap/status thread. The next useful #106 work should be a
fresh owner-gated packet for one of:

- cross-node application of `scripts/deploy-gte-int8-embedding.sh`;
- bounded shadow-evidence rerun after model/runtime changes;
- regression/RSS checks after dependency or deployment changes.
