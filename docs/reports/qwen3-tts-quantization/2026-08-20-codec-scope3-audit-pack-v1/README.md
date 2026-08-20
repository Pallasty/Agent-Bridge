# Qwen codec scope-3 quantization audit pack v1

This is the first self-contained pack produced by the unified offline TTS
quantization candidate workflow. Its inputs are exact copies of the frozen E25
waveform evidence, E26 blinded owner review and four-case manifest, and E27
end-to-end runtime reduction.

Decision: `reject`.

- Waveform numeric evidence: `PASS` on 4/4 cases.
- Blind listening evidence: `PASS` on 4/4 cases.
- Runtime evidence: `FAIL`, covers only 2/4 cases.
- Runtime memory delta: positive, so memory usage regressed.
- Operational authorization: all fields remain `false`.

The decision does not dispute the observed audio quality. It prevents promotion
because the tested runtime path supplied no end-to-end resource benefit and did
not cover the full frozen corpus. No new quantization or inference is authorized
by this pack.

Reproduce the decision from within this directory:

```bash
python ../../../../scripts/eval/tts_quantization_gate.py \
  --manifest candidate.manifest.json \
  --policy gate.policy.json \
  --output /tmp/qwen-codec-scope3-recheck.json
```

Expected exit code: `2`. Expected manifest SHA-256:
`56ffa8be983974455fe6286627cefa7cdcf5504c2d6ca28f6042d768749a1408`.
