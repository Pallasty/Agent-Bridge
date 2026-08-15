# ADR-0010: Qwen TTS quantization toolchain and MI50 separation

- Status: Accepted
- Date: 2026-07-30
- Depends on: ADR-0008, ADR-0009, S5R

## Context

The acquired Qwen model weights now match the immutable official revision.
The community ONNX snapshot also contains converter source and existing
FP32/FP16/INT4 artifacts, but its build environment is not reproducible:

- only `transformers==4.57.3` is exact in the PEP 723 declaration;
- Olive, Torch, ONNX, ONNX Runtime, and other dependencies float;
- `requirements.txt` requests `transformers>=5.10`, conflicting with the
  converter's exact inline requirement;
- `uv` is not installed on the host;
- the converter writes beneath its own `onnx/` directory and replaces existing
  files, so it must never run inside the downloaded community snapshot; and
- without `--skip-download`, it can make an implicit Hugging Face download.

The converter implements Olive block-wise RTN weight quantization at four bits,
block size 32, asymmetric. Codec graphs and the speaker encoder stay FP32.
Existing CUDA manifests are NVIDIA execution-provider declarations and do not
constitute ROCm or MI50 evidence.

For the manifest-declared CPU payload only, the existing community FP32 graphs
occupy 8,640,579,071 bytes and INT4 graphs 1,962,288,831 bytes: 4.403× smaller,
or a 77.29% reduction. Stale unlisted files are excluded. This is storage
evidence only and does not establish quality, parity, or runtime speed.

## Decision

Use the community converter only as audited source material. Before execution,
copy the minimum hash-bound source into a new isolated workspace and create a
complete offline dependency lock.

The reference and quantization order is:

1. export the fixed-source CPU FP32 component lane;
2. verify component and greedy generation parity;
3. export CPU INT4 with Olive block-wise RTN;
4. quantify FP32-to-INT4 token, logit, frame, and perceptual drift; and
5. only then evaluate an MI50 inference lane.

The initial quantizer is
`olive_onnx_blockwise_rtn_int4_after_fp32_reference`. AMD Quark remains a
research watch option, not the initial path: it adds a second unpinned toolchain
and does not remove the need for a proven FP32 reference.

## MI50 boundary

MI50 is gfx906. ROCm 5.7 was the final fully supported gfx906 release. Keep MI50
runtime validation in a separate, legacy ROCm container lane; do not label CUDA
artifacts as AMD-compatible.

The existing `arrowquant-rocm:5.7` image is rejected for this TTS lane. It has
no repository digest, its default command installs packages, its history
contains a Cloudflare WARP setup, and it does not identify Olive or ONNX
Runtime versions. It may remain for its original workload but is not a
reproducible Qwen TTS quantizer.

## Consequences

S5S completes the static audit but intentionally reports
`audited_lock_and_execution_blocked`. The next gate must create a pinned,
offline environment specification and isolated workspace without running the
converter. Converter execution, ONNX creation, GPU use, parity, and model
adoption remain separately authorized.
