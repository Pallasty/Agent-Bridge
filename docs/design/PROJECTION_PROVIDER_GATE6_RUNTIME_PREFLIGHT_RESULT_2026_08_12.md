# Projection Provider Gate 6: ABot-World Runtime Preflight

Date: 2026-08-12

## Scope

Gate 6 adds a dependency-free runtime preflight at
`scripts/preflight_abot_world_runtime.py`. It checks the official runtime
boundary before any model load or inference attempt.

The preflight is fail-closed. A blocked result exits with code 2 and records
`load_attempted=false`, `inference_attempted=false`, and
`runtime_admitted=false`.

## Local result

Checkpoint files were present, but the host did not satisfy the upstream
runtime requirements:

| check | result |
| --- | --- |
| operating system | macOS Darwin |
| architecture | Apple arm64 |
| GPU | Apple M2 Ultra / Metal 4 |
| NVIDIA CUDA probe | `nvidia-smi` not found |
| Python | 3.9.6 |
| required Python modules | `torch`, `diffusers`, `transformers`, `accelerate`, `safetensors` absent |
| upstream target | Ubuntu 22.04, CUDA 13.3, NVIDIA RTX 5090 |

The model README states that the released path was tested on an NVIDIA RTX
5090 with approximately 19 GB GPU memory. No equivalent CUDA runtime is
available on this host. Installing arbitrary CPU or Metal dependencies would
not establish compatibility with the published inference path, so no install
or load attempt was made.

## Verification

```text
python3 -m unittest tests/test_abot_world_runtime_preflight.py -v
2 passed

python3 -m py_compile scripts/preflight_abot_world_runtime.py
git diff --check
```

The real-directory preflight returned:

```text
official_runtime_target_is_linux
official_runtime_target_is_x86_64
nvidia_gpu_unavailable
python_3_12_required_by_upstream_setup
missing_python_modules:torch,diffusers,transformers,accelerate,safetensors
```

## Boundary verdict

`GATE6_ABOT_RUNTIME_PREFLIGHT_BLOCKED_HOST_INCOMPATIBLE`

This is an environment boundary, not evidence that the checkpoint is corrupt.
The next viable execution gate requires an authorized Linux x86_64 CUDA host
with a supported NVIDIA GPU, or a separately validated upstream-compatible
port. Until then ABot-World remains an offline projection asset and is not an
Agent-Bridge runtime provider.
