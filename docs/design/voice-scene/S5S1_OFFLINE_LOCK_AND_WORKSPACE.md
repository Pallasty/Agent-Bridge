# S5S1 offline lock and isolated workspace

S5S1 turns the S5S audit result into a fail-closed preparation contract. It
does not claim that a complete offline environment exists.

## Selected baseline

The CPU conversion lane selects CPython 3.12.13, PyTorch 2.12.0 CPU,
TorchVision 0.27.0 CPU, Transformers 4.57.3, Olive 0.13.0, ONNX 1.21.0, and
ONNX Runtime 1.27.0 as exact critical direct inputs.

PyTorch 2.12.0 is retained because the audited community converter explicitly
targets its dynamic-shape behavior. The official PyTorch 2.12 CPU recipe pairs
it with TorchVision 0.27.0 and does not include TorchAudio. TorchAudio is also
not imported by the selected converter, so it is excluded. ONNX Runtime GenAI
is excluded because its ModelBuilder path was rejected for this Qwen TTS
talker and is not used by the selected Olive converter.

Olive 0.13.0 is a selected current candidate compatible with the converter's
time window, not recovered evidence of the environment used by the community
publisher. The later dry-run gate must still verify that the converter's
`OnnxBlockwiseRtnQuantization` pass spelling is accepted by this Olive version.

Primary release references:

- <https://www.python.org/downloads/release/python-31213/>
- <https://pytorch.org/get-started/previous-versions/>
- <https://pypi.org/project/olive-ai/0.13.0/>
- <https://pypi.org/project/onnx/1.21.0/>
- <https://pypi.org/project/onnxruntime/1.27.0/>
- <https://pypi.org/project/transformers/4.57.3/>

## Honest lock boundary

`critical_direct_pins_exact=true` means only that the seven selected direct
inputs have exact versions. It does not mean that a resolver has produced the
complete transitive environment. Until all compatible CPython 3.12 x86-64
wheels are materialized and SHA-256 recorded:

- `transitive_lock_complete=false`
- `wheel_hash_ledger_complete=false`
- `offline_install_ready=false`
- `converter_execution_ready=false`

The eventual install command must use `--no-index`, a dedicated wheelhouse,
and `--require-hashes`. S5S1 intentionally emits no converter command.

## Isolation boundary

The future workspace, wheelhouse, and virtual environment must be absent and
pairwise disjoint. They must not overlap the original ModelScope model, the
currently usable community ONNX snapshot, or the audited community converter.
The converter must be copied into `workspace/source` and write only beneath
`workspace/output`; it must never execute in the community snapshot.

The receipt records the planned paths and a 128 GiB free-space policy floor.
Generating the receipt does not create those paths.

## Next gate

S5S2 may materialize the wheelhouse only as a separately reviewed operation.
It must:

1. resolve all transitive dependencies for CPython 3.12 x86-64;
2. fail if any package lacks an admitted wheel;
3. hash every wheel and produce a fully hashed lock;
4. install only from that wheelhouse into the isolated virtual environment;
5. run import/pass-registration checks without loading the model;
6. keep converter execution separately blocked.

Large PyTorch wheel acquisition is therefore visible as a distinct storage and
network action rather than hidden inside converter execution.
