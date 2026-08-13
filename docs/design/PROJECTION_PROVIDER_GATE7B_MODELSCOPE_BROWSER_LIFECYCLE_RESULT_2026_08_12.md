# Projection Provider Gate 7B: ModelScope Browser Lifecycle

Date: 2026-08-12

## Result

The public ABot-World ModelScope Studio completed one bounded browser-owned
iframe/WebSocket lifecycle from the current Mac:

1. The start action disabled the start control, enabled the stop control, and
   created one session iframe.
2. The iframe progressed from the GPU queue to a visible generated stream.
3. The stream reported up to `117/120` generated blocks, `1404` frames, and
   `11.8 FPS` during the observation window.
4. The stop action removed the iframe, reported `已停止`, and restored the
   enabled start control.

The sanitized evidence receipt is:

```text
docs/design/evidence/modelscope_abot_gate7b_browser_receipt_2026_08_12.json
```

It intentionally excludes the prompt text, transient session identifier, and
screenshots. No credential was used or recorded.

## Validator

The default-off adapter now validates browser lifecycle receipts without
starting a Studio session:

```text
python3 scripts/modelscope_abot_provider.py \
  --validate-browser-receipt \
  docs/design/evidence/modelscope_abot_gate7b_browser_receipt_2026_08_12.json
```

Validation fails unless start, positive-FPS stream, stop, zero post-stop
iframes, and restored readiness are all present. It also rejects receipts that
claim runtime admission or rollout emission.

## Evidence boundary

The browser proved a real streaming lifecycle, but it did not capture a durable
model-native frame or video artifact with a content hash. A screenshot of the
Studio UI is presentation evidence, not the generated artifact itself.
Therefore no `SimulatedWorldRollout` was emitted and the provider remains
default-off and unregistered.

## Verdict

`GATE7B_MODELSCOPE_BROWSER_LIFECYCLE_VERIFIED_ARTIFACT_NOT_BOUND_RUNTIME_NOT_ADMITTED`

The next gate is an artifact-capture contract that obtains a provider-produced
frame or video, hashes it, and binds it to a projection request before rollout
eligibility can be evaluated.
