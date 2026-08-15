# ADR-0006: S5 Chinese voices are auditioned before character binding

- Status: accepted for S5A implementation
- Date: 2026-07-29
- Exit state for this unit: `chinese_voice_audition_contract_ready`
- Full S5 exit remains: `story_chinese_multispeaker_verified`

## Decision

S5 separates model capability, machine intelligibility, and human voice
judgment. A backend may render valid audio without being eligible for character
binding. Narrator and character profiles are versioned and use opaque speaker
IDs; speaker gender, identity, and role fit are never inferred from the numeric
ID.

AISHELL-3 is the CPU multi-speaker baseline. Qwen3 CustomVoice remains the
expressive candidate. They are not treated as interchangeable: the former has
174 opaque speakers but no instruction-emotion lane, while the latter supports
named presets and instructions with a materially heavier runtime.

## Gates

`story_voice_audition.py` builds a deterministic three-voice blinded plan using
the same Chinese reference text. Promotion requires:

- one narrator and two character roles bound to distinct speaker IDs;
- a machine-verified artifact hash for every item;
- Chinese ASR character error rate at or below 0.20;
- owner scores of at least 3/5 for audibility, intelligibility, naturalness,
  and role fit;
- all three voice pairs confirmed distinguishable;
- an explicit assertion that no real-person voice clone was used.

The review result never writes canon. Human review receipts remain proposals
until explicitly persisted by the owner-controlled Agent-Bridge lane.

## Provenance and licensing

The inspected official AISHELL-3 release archive is 31,559,701 bytes with
SHA-256
`ab468db3a3308cdd861495e0db2f25d79418a0c00639f74944c7cdf5dd8c6ec1`.
It contains no license file. Repository licensing is not silently inherited by
model weights, so local evaluation is allowed but production promotion and
redistribution remain blocked until model-weight licensing is verified.

Qwen3-TTS is tracked separately using the already-audited model hashes and
Apache-2.0 upstream source. Its prior single-voice success is not evidence of
three-role distinguishability or stable long-form character performance.

## Non-claims

S5A downloads no runtime model, installs no backend, renders no audition audio,
plays nothing, and enables no service. The temporary archive inspection is
evidence only. Full S5 requires real three-voice rendering, Chinese ASR
verification, blinded owner audition, and version-bound character mappings.
