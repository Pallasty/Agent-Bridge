# S5Q fixed-source offline acquisition packet

S5Q prepares, but does not execute, acquisition from official immutable Qwen
revision `6c3e96b6a2c593ce3e546ee699a5d944de81850e`.

## Isolated destination

The reserved destination is:

```text
/4TNVMe2/aiot_weights/qwen3_tts/original/Qwen3-TTS-12Hz-1.7B-CustomVoice/6c3e96b6a2c593ce3e546ee699a5d944de81850e
```

It is deliberately outside the existing ONNX ModelScope snapshot. The
planner fails closed if the destination already exists or overlaps that
snapshot.

## Small-file-only command

Run this only when an online machine has the Hugging Face CLI installed:

```bash
hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
  --revision 6c3e96b6a2c593ce3e546ee699a5d944de81850e \
  --include .gitattributes \
  --include README.md \
  --include config.json \
  --include generation_config.json \
  --include merges.txt \
  --include preprocessor_config.json \
  --include tokenizer_config.json \
  --include vocab.json \
  --include speech_tokenizer/config.json \
  --include speech_tokenizer/configuration.json \
  --include speech_tokenizer/preprocessor_config.json \
  --local-dir /4TNVMe2/aiot_weights/qwen3_tts/original/Qwen3-TTS-12Hz-1.7B-CustomVoice/6c3e96b6a2c593ce3e546ee699a5d944de81850e
```

The allowlist contains no `.safetensors` path. S5Q intentionally emits no
weight-download command.

After acquisition, generate a transport ledger with `sha256sum` over the 11
allowlisted paths. Those observed hashes must be persisted and reviewed before
B0 can be called complete; S5Q does not invent expected hashes while direct
fixed-revision transport is unavailable.

## Capacity policy

The two future weight files total 4,515,695,644 bytes. The planner additionally
requires at least 128 GiB free at the destination filesystem as a conservative
workspace floor for later isolated export work. This is a policy threshold,
not an estimate that FP32 export will consume exactly 128 GiB.

Weight acquisition, converter execution, parity testing, and adoption remain
separate later stages.
