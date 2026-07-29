# Voice Scene S0 contract

Voice Scene is Agent-Bridge's shared event contract for story performance,
meeting reconstruction, and multi-agent theatre. S0 defines the data and
validation boundary only. It does not synthesize or record audio, load models,
write memories or forum posts, or mutate a running Agent-Bridge instance.

## Static commands

```bash
python3 scripts/voice_scene_contract.py validate \
  docs/design/voice-scene/fixtures/story.json --pretty

python3 scripts/voice_scene_contract.py plan \
  docs/design/voice-scene/fixtures/meeting.json --pretty
```

Both commands read one JSON document and print JSON to stdout. `validate`
returns a non-zero status for semantic contract violations. `plan` returns a
bounded summary whose status is `contract_ready_no_runtime`.

## S0 acceptance surface

- One schema covers `story`, `meeting`, and `agent_theater`.
- Sources carry exact content hashes and explicit versions.
- Timeline order and idempotency keys are deterministic and validated.
- Speaker identity and versioned voice profiles are separate.
- Claims distinguish source truth, observation, inference, and simulation.
- Simulation branches cannot write into the canonical branch.
- Every runtime-effect flag is required to be `false`.

The JSON Schema checks document shape. The Python validator checks
cross-reference and provenance invariants that JSON Schema alone cannot
express. A packet is S0-valid only when it passes both.

## Files

- `voice_scene.schema.json`: Draft 2020-12 interchange schema.
- `story_plan.schema.json`: S1 static story-ingest and review schema.
- `story_render_manifest.schema.json`: S2 segment/chapter render evidence.
- `character_state.schema.json`: S3 ledger and resume snapshot contract.
- `realtime_interaction.schema.json`: S4 PTT turn receipt and owner gates.
- `fixtures/story.json`: novel-performance contract example.
- `fixtures/story_s1.md`: deterministic TXT/Markdown ingest sample.
- `fixtures/meeting.json`: meeting reconstruction contract example.
- `fixtures/agent_theater.json`: multi-agent scene contract example.
- `ADR-0001-voice-scene-contract.md`: architecture decision and boundaries.
- `NOVEL_TTS_V1_MIGRATION.md`: mapping from the existing novel prototype.
- `ADR-0003-story-offline-render.md`: cache, assembly, and playback gates.
- `ADR-0004-memory-grounded-character-state.md`: knowledge and branch gates.
- `ADR-0005-realtime-story-interaction.md`: realtime state and consent gates.

## S4 realtime story interaction

`scripts/story_realtime_interaction.py` provides a bounded push-to-talk turn
orchestrator. It pauses the story, captures only with explicit microphone
authorization, routes the stable transcript through S3 grounding and spoiler
checks, renders a response, emits it only under a separate output gate, and
resumes the exact playback position.

Fixture tests do not open a microphone or sound device. A real closed-loop
trial remains a separate explicit owner-authorized acceptance action.

For retained session artifacts, `withdraw_artifacts()` requires separate owner
authorization and deletes only the explicitly named files; directories and
unrelated session files are never recursively removed.

## S3 memory-grounded character state

`scripts/story_character_state.py` provides append-only canon, character
knowledge, and interaction ledgers; cursor-bounded `/story ask`; a spoiler
falsifier; inferential psychological profiles; and deterministic session
snapshot/resume projections.

```bash
python3 scripts/story_character_state.py /story ask \
  --snapshot docs/design/voice-scene/fixtures/s3/character_state.json \
  --character character_lin \
  --question '钥匙在哪里？'
```

S3 is text-only. Story state snapshots retain
`proposal_only_owner_review_required` and do not silently write simulations or
unreviewed story facts into global AB memory.

## S2 offline render

`scripts/story_offline_render.py` provides the render-only contract,
version-bound segment cache, bounded retry, PCM WAV validation, chapter
assembly, integrity verification, and `ChapterPlayer` state machine.

Playback is never implicit. `ChapterPlayer.start()` and `.resume()` require an
explicit owner authorization argument. Machine-verified WAV output remains
`human_audition=pending` until the owner listens to that exact artifact.

## S1 static story ingest

```bash
python3 scripts/story_static_ingest.py \
  /story docs/design/voice-scene/fixtures/story_s1.md chapter 2 --pretty
```

The command prints a deterministic, reviewable story plan. It does not create
an output file. Character, relationship, event, and emotion extraction is
deliberately heuristic and remains in `needs_review`.
