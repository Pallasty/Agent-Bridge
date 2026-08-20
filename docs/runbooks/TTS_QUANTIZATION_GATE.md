# TTS quantization offline gate

This gate turns producer-native Qwen or OmniVoice evidence into one closed-world,
hash-bound decision receipt. It is deliberately offline and non-authorizing: it
cannot write weights, generate or play audio, wire a runtime, deploy, or promote
a candidate.

For routine candidate onboarding, prefer
`scripts/eval/tts_quantization_candidate_workflow.py`. It creates an exclusive
`0700` self-contained audit-pack directory containing `0600` exact copies of the
native evidence, corpus, policy, normalized manifest, and receipt. Moving the
directory does not break its relative references or hash verification.
The lower-level adapter and gate commands below remain useful for diagnosis.
Only manifests emitted by a reviewed native adapter are admission inputs. The
generic gate binds and evaluates normalized claims but intentionally does not
reinterpret arbitrary producer schemas; a hand-authored manifest can never be
used as promotion authority, and every receipt keeps all operational authority
fields false.

## Decisions

- `pass`: every component-boundary check and resource check passed.
- `reject`: at least one measured quality or resource check failed.
- `insufficient_evidence`: no measured failure exists, but required coverage is
  missing. Static entropy evidence is shadow-only and never admits a candidate.

The process exit code is `0` for `pass`, `2` for either non-passing decision, and
an argparse error for an invalid or hash-mismatched contract.

## Qwen codec example

```bash
python scripts/eval/tts_quantization_candidate_workflow.py qwen-codec-scope3 \
  --waveform tests/fixtures/tts_quantization/qwen_waveform.json \
  --listening tests/fixtures/tts_quantization/qwen_listening.json \
  --runtime tests/fixtures/tts_quantization/qwen_runtime_rejected.json \
  --corpus tests/fixtures/tts_quantization/qwen_corpus.json \
  --policy scripts/eval/fixtures/tts_quantization_gate_policy_v1.json \
  --output-dir /tmp/qwen-tts-audit-pack
```

The workflow exits `2` for a valid rejection or insufficient-evidence receipt.
Inspect `candidate.receipt.json`; do not treat every nonzero exit as malformed
input. An existing output directory is never reused or overwritten.

Equivalent lower-level commands:

```bash
python scripts/eval/tts_quantization_manifest_adapter.py qwen-codec-scope3 \
  --waveform tests/fixtures/tts_quantization/qwen_waveform.json \
  --listening tests/fixtures/tts_quantization/qwen_listening.json \
  --runtime tests/fixtures/tts_quantization/qwen_runtime_rejected.json \
  --corpus tests/fixtures/tts_quantization/qwen_corpus.json \
  --output /tmp/qwen-tts-candidate.json

python scripts/eval/tts_quantization_gate.py \
  --manifest /tmp/qwen-tts-candidate.json \
  --policy scripts/eval/fixtures/tts_quantization_gate_policy_v1.json \
  --output /tmp/qwen-tts-gate-receipt.json
```

The frozen sample is expected to reject because the native runtime experiment
increased memory and covered only two of four cases. This is a regression
fixture, not a recommended candidate.

## OmniVoice example

```bash
python scripts/eval/tts_quantization_manifest_adapter.py omnivoice-static-int8 \
  --summary tests/fixtures/tts_quantization/omnivoice_static_rejected.json \
  --trajectory tests/fixtures/tts_quantization/omnivoice_trajectory_rejected.json \
  --output /tmp/omnivoice-candidate.json

python scripts/eval/tts_quantization_gate.py \
  --manifest /tmp/omnivoice-candidate.json \
  --policy scripts/eval/fixtures/tts_quantization_gate_policy_v1.json \
  --output /tmp/omnivoice-gate-receipt.json
```

The frozen sample is expected to reject both the one-step numeric comparison
and full autoregressive trajectory. Runtime evidence is also absent.

Outputs use exclusive creation with mode `0600`; choose a new output path for
every run. Producer evidence and corpus bytes are SHA-256 bound in the manifest,
and manifest and policy bytes are SHA-256 bound in the receipt.
