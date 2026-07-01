# Thread 106 GTE Embedding RAM Status Audit

Date: 2026-07-01

Status: `READ_ONLY_STATUS_AUDIT / NO_RUNTIME_CHANGE / NO_DB_WRITE`

## Decision

Do not merge or deploy any old embedding-quantization branches from thread #106
as an automatic next step.

The core #106 pain point, gte-768 double-loading in `daemon` and `daemon-http`,
is already represented in current `master` by:

- `RemoteEmbedBackend` opt-in embedding delegation;
- per-node gte embedding-only INT8 deployment scripts;
- `embedding_quant_shadow` as a read-only diagnostic surface.

The current local node is configured for the RAM-saving path and verifies ready.
Thread #106 should remain open as a roadmap/coordination surface, not as an
implicit merge queue.

## Evidence

Current repo state:

```text
## master...origin/master
HEAD a99548f docs(memory): refresh thread 90 sepl audit anchor
```

Thread #106 readout:

| Post | Current meaning |
|---|---|
| #2565-#2568 | Track A investigated stored-vector INT8. Codec worked, but storage ROI was negligible because embeddings were about 1% of the DB. Track A should stay parked unless corpus size changes materially. |
| #2569-#2572 | Track B identified and packaged the real RAM levers: embedding-only INT8 ONNX model plus daemon to daemon-http embedding delegation. |
| #2650 | `embedding_quant_shadow` landed on `origin/master` as read-only / measurement-only. |
| #2652-#2654 | Deployment was verified, with an older stale-MCP caveat that has since been superseded by current doctor/lifecycle checks. |

Current code and branch state:

| Check | Result |
|---|---|
| `crates/bridge/src/remote_embed.rs` | present; `RemoteEmbedBackend` delegates to `/embed` with local fallback |
| `crates/bridge/src/main.rs` daemon arm | installs delegation when `AGENT_BRIDGE_EMBED_REMOTE_URL` is set |
| `crates/bridge/src/main.rs` daemon-http arm | does not install delegation, preventing self-loop |
| `scripts/deploy-gte-int8-embedding.sh` | present; idempotent per-node drop-in deploy with `--rollback` |
| `scripts/quantize_gte_embedding_int8.py` | present |
| `scripts/wrapper/machine.env.example` | documents the optional int8/delegation env |
| local branches | only archive refs remain for old `feat/embed-int8-quant` and old daemon delegation shape |
| remote branch | `origin/feat/gte-embedding-ram` remains as an audit/source branch, not an active local merge candidate |

Current runtime readout:

| Check | Result |
|---|---|
| `agent-bridge.real doctor --json` | `ok=true`, `fails=0`, `warns=0`; 11 MCP servers all executing current `.real` |
| `mcp_lifecycle_digest` | lifecycle `ready`, readiness `ready`, runtime health `ready`, failing tools `0` |
| `/healthz` | daemon-http and Palace both `ok` |
| filtered env, daemon | `AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models-int8`; `AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed` |
| filtered env, daemon-http | `AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models-int8` |
| `/embed` probe | returned `backend=gte-multilingual-base`, `dim=768` |
| RSS after probe | daemon about 8 MB; daemon-http about 548 MB |

The `/embed` response contained an embedding vector; this report records only
the non-sensitive metadata needed for status verification.

## Interpretation

The important distinction is:

- Track A stored-vector INT8 is technically viable but low ROI on this node and
  should not be reactivated from archived branches without a fresh storage-size
  trigger and owner gate.
- Track B RAM reduction is the meaningful path and is already present in current
  code and current node configuration.
- `embedding_quant_shadow` remains a diagnostic surface only. It does not change
  retrieval order, drop f32 vectors, or serve INT8 vectors from the store.
- The older stale-MCP caveat in #2652/#2654 is obsolete for this session; current
  doctor and lifecycle checks are clean.

## Safe Next Shapes

1. Keep #106 open as a roadmap/status thread, not as an active implementation
   queue.
2. If more work is desired, use a fresh owner-gated packet for one of:
   - cross-node application of `scripts/deploy-gte-int8-embedding.sh`;
   - a bounded rerun of `embedding_quant_shadow` evidence;
   - Track B quality/RSS regression evidence after a model/runtime upgrade.
3. Do not merge archive refs:
   - `archive/parked-embed-int8-quant-20260630`;
   - `archive/obsolete-daemon-embed-delegation-20260630`.

## Boundary

This audit did not:

- change systemd drop-ins or environment;
- restart services;
- write memory rows, graph edges, schemas, or embedding blobs;
- run a reindex;
- change retrieval ranking or model selection;
- merge, delete, or archive branches.
