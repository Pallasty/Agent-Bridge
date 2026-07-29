# Novel TTS embodied v1 migration map

The existing `prototypes/novel_tts_embodied/v1` remains a prototype and is not
silently promoted into the Voice Scene runtime. S0 maps its useful concepts
into the shared contract while explicitly rejecting unverifiable behavior.

| Prototype concept | Voice Scene S0 target | Migration rule |
| --- | --- | --- |
| input novel/file | `sources[]` | Record URI, exact SHA-256, and edition/version before parsing. |
| parsed segment | `timeline[]` utterance | Assign contiguous sequence, stable event ID, idempotency key, and source locator. |
| narrator/character | `speakers[]` | Preserve a stable identity; aliases do not create new speakers. |
| inferred gender voice slot | no direct equivalent | Do not collapse identity to gender. Create a versioned profile requiring review. |
| voice assignment | `voice_profiles[]` | Preserve backend/model/voice/version separately from speaker identity. |
| emotion/style hint | observation or inference claim | Include evidence and confidence; never store it as source truth. |
| synthesized output | planned `render_artifact` event | S0 may describe an artifact but may not claim that audio exists. |
| playback/presentation call | future renderer adapter | No direct S0 call; requires a later, verified render contract. |
| interaction log | proposed `memory_event` | Keep on its branch; S0 cannot write it to AB memory. |
| character continuation | simulation branch | Fork explicitly from a canonical event; never rewrite canon. |

## Compatibility gate

An old prototype run is not Voice Scene compatible merely because it produces
an audio file. Migration requires:

1. a packet that passes the JSON Schema and semantic validator;
2. stable source, speaker, branch, event, and claim references;
3. no placeholder marked as verified output;
4. no unreviewed voice assignment presented as character identity;
5. all S0 runtime-effect flags set to `false`.

`backend=ab-tts`, prototype-specific presentation arguments, or a successful
prototype regression are not evidence of an S0 runtime integration. A later
stage must specify and test the renderer boundary before those calls can be
adapted.
