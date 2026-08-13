# Projection Provider Gate 5: ABot-World Artifact Probe

Date: 2026-08-12

## Scope

Gate 5 adds a dependency-free, offline artifact inventory for the local
ABot-World checkpoint. The probe is at:

```text
scripts/probe_abot_world_artifact.py
```

It reads directory metadata and the small JSON configuration files. It does
not import PyTorch or any model package, open weights for inference, allocate
GPU memory, or register a provider.

## Local result

Probe input:

```text
/Users/pallasting/.cache/modelscope/models/amap_cvlab--ABot-World-0-5B-LF/snapshots/master
```

Observed result:

| field | value |
| --- | --- |
| schema | `agent_bridge.abot_world_artifact_probe.v0` |
| files | 15 |
| total bytes | 24,765,868,050 |
| manifest hash | `826a8e720fa9addbca7347bb441a1bd08460bdd2767f13706072a4dd7bd255d7` |
| model loaded | `false` |
| inference executed | `false` |
| runtime admitted | `false` |
| weight content hashed | `false` |

The metadata reported `WanModel`, `ti2v`, PyTorch, and `any-to-any`. The large
weight files are inventoried by path and size only in the default mode.
Content hashing is an explicit `--hash-content` option and remains separate
from loading or executing the model.

## Verification

```text
python3 -m unittest tests/test_abot_world_artifact_probe.py -v
3 passed

python3 -m py_compile scripts/probe_abot_world_artifact.py
git diff --check
```

The real-directory invocation completed with the manifest above:

```text
python3 scripts/probe_abot_world_artifact.py \
  /Users/pallasting/.cache/modelscope/models/amap_cvlab--ABot-World-0-5B-LF/snapshots/master \
  --output /tmp/abot-world-artifact-probe.json
```

## Admission boundary

Verdict: `GATE5_ABOT_ARTIFACT_PROVENANCE_VERIFIED_RUNTIME_NOT_ADMITTED`.

This proves local asset provenance and supports a future offline adapter
experiment. It does not prove model compatibility, inference performance,
generated visual quality, GPU availability, or projection-provider readiness.
The next gate is an explicitly bounded offline model load/inference probe only
if runtime dependencies and GPU constraints are separately accepted.
