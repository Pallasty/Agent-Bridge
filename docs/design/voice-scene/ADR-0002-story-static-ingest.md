# ADR-0002: S1 story ingest is deterministic and review-first

- Status: accepted for S1
- Date: 2026-07-29
- Exit state: `story_plan_reviewable`

## Decision

The first `/story` surface is a static planner:

```text
/story <path> from-start
/story <path> chapter <N>
```

It accepts UTF-8 TXT and Markdown. EPUB and PDF remain deferred adapters.
Playback, recording, model download, memory write, and runtime options fail
closed.

Exact source bytes determine the source fingerprint. Chapter IDs, speaker IDs,
voice-profile IDs, extracted-event IDs, review IDs, and Voice Scene event IDs
are content-derived. Repeating ingest against unchanged bytes and the same
source version produces the same plan.

## Evidence boundary

Chapter headings and line/character spans are source-grounded. Character names,
aliases, relations, actions, and emotions are heuristic candidates:

- character identity remains `needs_review`;
- every voice profile is per-character, versioned, and `unassigned`;
- relations and extracted events retain source spans and confidence;
- low-confidence emotion markers enter the review queue;
- no gender field is inferred or used to choose a voice.

The output embeds an S0 Voice Scene packet for the selected chapters. The S1
schema and S0 semantic validator are both required gates.

## Legacy boundary

The old `novel_tts_embodied/v1` data can provide text and annotations, but S1
rejects placeholder output marked verified, live playback arguments, and direct
`ab-tts` backend promotion. Render integration belongs to S2.

## Non-goals

S1 does not claim literary-grade entity resolution, coreference resolution,
emotion recognition, audio generation, live interaction, durable memory
ingest, EPUB/PDF support, or production `/story` MCP registration.
