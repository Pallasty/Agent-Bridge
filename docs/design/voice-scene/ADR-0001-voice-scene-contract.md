# ADR-0001: One Voice Scene contract before runtime integration

- Status: accepted for S0
- Date: 2026-07-29
- Stage: `contract_ready_no_runtime`

## Context

Story performance, meeting reconstruction, and multi-agent theatre share the
same hard problems: source provenance, stable speaker identity, ordered
utterances, interpretations with uncertainty, alternate branches, and
versioned voice projection. Building separate pipelines would make claims and
memory writeback semantics diverge before any runtime backend is selected.

## Decision

Agent-Bridge will use one `agent_bridge.voice_scene.v0` envelope with
mode-specific content. The contract separates:

1. source identity and immutable source fingerprint;
2. speaker identity and versioned voice profile;
3. canonical timeline and explicit alternate branches;
4. source truth, observation, inference, and simulation claims;
5. planned render artifacts and later runtime execution.

Deterministic identifiers use canonical JSON and SHA-256. Source fingerprints
bind exact bytes to an explicit edition/version. Timeline sequences must be
contiguous and idempotency keys unique within a packet.

Claims may become less certain but not more certain through derivation:
`source_truth` may only derive from `source_truth`. Inference is never silently
promoted to fact. Simulation claims must remain on simulation branches, and
events on simulation branches may not target the canonical branch.

## Offline and realtime lanes

The contract is lane-neutral. Offline story preprocessing may produce a
complete stable timeline. Realtime meetings may append provisional transcript
observations before later stabilization. Both lanes preserve the same IDs,
source references, claim kinds, and branch rules.

S0 does not define streaming transport, latency budgets, diarization or TTS
backend APIs. Those are later-stage adapters around this contract.

## Runtime boundary

All six effects are explicit and fail closed in S0:

- audio emission;
- audio recording;
- memory writes;
- forum writes;
- runtime mutation;
- model downloads.

Every flag must be present and `false`. The static CLI reads JSON and writes
only its result to stdout.

## Consequences

The three initial scenarios can share validation, fixtures, and later adapters.
Provenance and branch safety are testable before any voice model is chosen.
The cost is an intentionally narrow first milestone: S0 demonstrates contract
readiness, not audible quality or live integration.

## Deferred decisions

- speech recognition, diarization, translation, and TTS model selection;
- consent, retention, redaction, and access-control enforcement;
- memory proposal review and commit protocol;
- streaming checkpoints, recovery, and latency objectives;
- render artifact storage and playback.
