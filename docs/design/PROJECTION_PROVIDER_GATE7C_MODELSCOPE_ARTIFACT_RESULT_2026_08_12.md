# Projection Provider Gate 7C: ModelScope Native Artifact

Date: 2026-08-12

## Result

One provider-native frame was extracted from the ABot-World Studio WebSocket
stream. CDP observed binary opcode `2` payloads containing a 24-byte transport
header followed by a complete JPEG. The retained frame is independently
decodable as JFIF JPEG at `1280x704`.

```text
artifact: docs/design/evidence/modelscope_abot_gate7c_provider_frame_2026_08_12.jpg
bytes: 95419
sha256: 3ecb04301af4a90b9be916609534c81792a793d0a803ff22b9ac9b5060fa58ad
```

This is the provider-transmitted image body, not a screenshot of the Studio UI.
The session was stopped after capture; the iframe count returned to zero and
the start control became available again.

## Request and rollout binding

The artifact receipt binds the frame to a projection request by request ID,
provider ID, prompt digest, requested output, content hash, and truth boundary:

```text
docs/design/evidence/modelscope_abot_gate7c_artifact_receipt_2026_08_12.json
```

The included `SimulatedWorldRollout` is eligible under the provider-neutral
minimum contract because it has a generated artifact hash and uses evidence
class `simulated.generated`. Its verdict is necessarily `not_verified`; it
claims no external-world effect and has no `verified_to` boundary.

The Studio began from a visible default reference scene. Since the public
surface does not expose an exact input artifact digest or runtime revision, the
receipt records those conditions as unverified rather than claiming pure
text-only generation or exact reproducibility.

## Validator

```text
python3 scripts/modelscope_abot_provider.py \
  --validate-artifact-receipt \
  docs/design/evidence/modelscope_abot_gate7c_artifact_receipt_2026_08_12.json
```

The validator fails closed on path traversal, missing or modified artifact
bytes, hash/size/JPEG mismatch, request-rollout identity drift, truth-boundary
promotion, or runtime-admission claims.

## Verdict

`GATE7C_MODELSCOPE_NATIVE_ARTIFACT_HASH_BOUND_SIMULATED_ROLLOUT_ELIGIBLE_RUNTIME_NOT_ADMITTED`

No MCP tool or background provider was registered. A later admission gate must
separately define retention, cancellation, provider availability, and user
authority before any runtime invocation can be exposed.
