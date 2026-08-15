# ADR-0009: Qwen fixed-source re-export provenance remediation

- Status: Accepted
- Date: 2026-07-30
- Depends on: ADR-0008 and S5O

## Context

S5O proved that the official Qwen configuration is structurally compatible
with the three inspected CPU INT4 ONNX graphs. It did not prove which upstream
Qwen revision produced the current ONNX artifacts. Reference-compatible
multi-frame generation therefore remains blocked.

The published ONNX repository upload commit
`0ac9e3de55c326eec31a3cdf3b2dcd98cc86ff82` identifies the base model as
`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`, but the inspected repository evidence
does not bind the artifacts to an upstream source revision. An unbound revision
string is insufficient: the evidence must attest that the named revision
produced the artifact under review.

## Decision

Choose path B, a new isolated export from official immutable Qwen commit
`6c3e96b6a2c593ce3e546ee699a5d944de81850e`, as the self-verifiable
provenance remediation path. Keep path A available only if the converter
publisher later supplies artifact-bound lineage evidence.

The staged path is:

1. B0: acquire and hash fixed-revision configuration, generation
   configuration, converter source, licenses, and manifests without weights.
2. B1: after separate owner authorization, acquire the exact fixed-revision
   model and speech-tokenizer weights into a new isolated directory.
3. B2: audit and pin the export toolchain; do not execute unaudited community
   Python.
4. B3: export a CPU FP32 reference lane first.
5. B4: establish component and full greedy parity, then measure quantization
   drift rather than treating INT4 as the reference.
6. B5: require separate authorization before adopting or replacing any current
   snapshot.

The minimum known weight payload is 4,515,695,644 bytes: 3,833,402,552 bytes
for `model.safetensors` plus 682,293,092 bytes for speech-tokenizer weights.
This is not a total workspace estimate; export intermediates and FP32 ONNX
artifacts require additional capacity.

## Machine gate

`scripts/story_voice_provenance_remediation_decision.py` consumes the S5O
receipt and explicit public-evidence facts. It fails closed if S5O is not the
expected safe-incomplete state. A revision alone cannot enable path A without
artifact-bound attestation.

The S5P receipt records the selected path, stages, blockers, and zero runtime
effects. It never downloads files, executes ONNX or converter code, changes the
existing snapshot, uses a GPU, plays audio, or writes AB memory/forum state.

## Consequences

S5P is a decision checkpoint, not a model-readiness promotion.
`reference_generation_ready=false` remains mandatory. The next unit may
prepare B0's exact offline acquisition manifest and verification command.
Weight acquisition, re-export, parity work, and snapshot adoption remain
separate authorization boundaries.
