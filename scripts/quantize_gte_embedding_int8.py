#!/usr/bin/env python3
"""Produce the deployable embedding-only INT8 gte-multilingual-base ONNX model.

Quantizes ONLY the ~250k-vocab embedding table (the `Gather` op, per-channel) to
int8 and leaves the transformer in fp32. On the real agent-bridge corpus this is
essentially lossless for retrieval (cos 0.9997, recall@10 0.980 vs fp32) while
cutting the ONNX session RSS ~1528MB -> ~956MB (~572MB/instance) and disk
1197MB -> 648MB. Full int8 (also quantizing the transformer MatMuls) would save
more but drops recall@10 to ~0.77 because gte uses CLS pooling — so we quantize
the embedding table only. See AB memory `arrowquant_b1_gte_qdq_spike_results`.

Needs `onnxruntime` + `onnx` (CPU only; no GPU). `deploy-gte-int8-embedding.sh`
bootstraps an ephemeral venv for this; or run it in any env that has them:

  python quantize_gte_embedding_int8.py [SRC_MODEL.onnx] [OUT_MODEL.onnx]

Defaults to the daemon's local bundle and writes <dir>/model.int8.onnx.
"""
import os
import sys

DEFAULT_DIR = os.path.expanduser(
    "~/.cache/agent-bridge/onnx-models/gte-multilingual-base"
)


def main():
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except Exception as e:  # pragma: no cover - environment guard
        sys.exit(
            f"onnxruntime not available ({e}). Install onnxruntime + onnx, or copy "
            "an already-generated model.onnx from a node that has it."
        )

    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DEFAULT_DIR, "model.onnx")
    out = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.join(os.path.dirname(src), "model.int8.onnx")
    )
    if not os.path.exists(src):
        sys.exit(f"source model not found: {src}")

    print(f"src: {src}  ({os.path.getsize(src) / 2**20:.0f} MB)")
    print("quantizing embedding table (Gather) to int8, per-channel; transformer fp32 ...")
    quantize_dynamic(
        src,
        out,
        weight_type=QuantType.QInt8,
        per_channel=True,
        op_types_to_quantize=["Gather"],
    )
    print(f"out: {out}  ({os.path.getsize(out) / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
