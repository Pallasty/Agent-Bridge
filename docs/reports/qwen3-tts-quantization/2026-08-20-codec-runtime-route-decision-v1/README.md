# Qwen codec runtime route decision v1

Status: `PAUSE_CURRENT_CODEC_RUNTIME_ROUTES`.

This self-contained decision reduces the frozen E21 packed-MPS, E22 Core ML,
and E27 end-to-end evidence. It does not authorize a checkpoint rewrite,
custom-kernel build, runtime wiring, deployment, or promotion.

## Closed routes

- Reversible sidecar: rejected. It retains 25,165,824 bytes of FP16 weights and
  adds a 12,595,968-byte sidecar, producing a 12,595,200-byte live-memory increase.
- Current packed MPS kernel: rejected. Worst module slowdown is 12.692x.
- Current Core ML handoff: rejected. Latency is 3.455x the MPS fake-Q8 path and
  kernel NRMSE is 0.002899, above the frozen 0.002 limit.
- Three-module checkpoint rewrite: deferred. The theoretical net model-memory
  saving is only 0.301%, below the 5% threshold for such an irreversible path.

Reopening requires a native fused kernel or equivalent runtime that does not
retain FP16 weights, at least 5% projected model-memory saving, full corpus
coverage, end-to-end latency no worse than 1.05x, negative runtime-memory delta,
and fresh waveform plus blinded-listening evidence.
