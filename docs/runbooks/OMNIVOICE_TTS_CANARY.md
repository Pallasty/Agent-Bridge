# OmniVoice TTS owner canary

## Safety boundary

The checked-in policy admits only `owner-local-pilot`, only plain Chinese or
English requests, and only ten percent of stable request-id buckets. Admission
does not enable execution by itself: `AB_TTS_CANARY_ENABLED=1` remains required
for every process. Named speakers, style instructions, reference cloning,
missing request ids, non-allowlisted subjects, and out-of-bucket requests stay
on the Qwen control backend.

The policy is cryptographically bound to the completed owner listening-review
decision. A missing, modified, malformed, synthetic, blocked, or
production-authorizing decision fails closed to Qwen. Candidate runtime errors
also fall back to Qwen and remain visible in the receipt.

## Explicit local invocation

```bash
AB_TTS_CANARY_ENABLED=1 \
AB_OMNIVOICE_TTS_ENABLED=1 \
AB_OMNIVOICE_TTS_PYTHON=/Data/.venvs/qwen3-tts-cpu/bin/python \
/Data/.venvs/qwen3-tts-cpu/bin/python scripts/audio_embody.py \
  --mode speech \
  --capture-channel synth_file \
  --synth-backend canary \
  --canary-subject owner-local-pilot \
  --canary-request-id owner-canary-9 \
  --voice auto \
  --omnivoice-manifest /Data/Models/onnx-controls/OmniVoice-staged-quantization/recommended-fp16-embeddings.json \
  --text '你好。' \
  --json
```

Unset `AB_TTS_CANARY_ENABLED` to roll back immediately. The production default
backend and service configuration are not changed by this canary.
