# Free Recall Strategy R3 — Prospective Episode Sidecar Preregistration

Date: 2026-07-21

Status: **PREREGISTERED / PUBLIC-SYNTHETIC ONLY / NO STORE OR RETRIEVAL AUTHORITY**

Parent result:
`docs/design/FREE_RECALL_STRATEGY_R2_EPISODE_RECOVERABILITY_RESULT_2026_07_21.md`

## 1. Question

R2 showed that episode membership cannot be recovered reliably from existing
AB tags, edges, or timestamps. R3 asks whether a prospective explicit sidecar
can preserve episode membership and position under realistic event-delivery
faults, and whether a fully valid episode can improve fixed-budget set recall
without allowing partial or conflicted episodes to influence retrieval.

This is a contract/admission experiment. Explicit positions are declared
metadata, not a learned index code, and R3 does not claim to replicate the
paper's recurrent representation.

## 2. Frozen event contract

Schema: `agent_bridge.episode_observation.v0`.

Every event has a globally unique `event_id`, opaque `episode_id`, and one
event type:

- `episode.open`: declares `source` as exactly `session`, `curation_batch`, or
  `owner_bundle`;
- `episode.item`: declares an opaque `item_id`, zero-based non-negative
  `episode_position`, and a public-synthetic `content_variant` used only by the
  falsifier;
- `episode.close`: declares `item_count` and marks the episode eligible for
  completeness validation.

Reducer rules:

- input order must not matter;
- replaying the same `event_id` with byte-identical payload is idempotent;
- reusing an `event_id` with a different payload conflicts the whole episode;
- one episode may have only one open and one close payload;
- positions and item IDs must each be unique within an episode;
- a closed episode finalizes only when positions are exactly
  `0..item_count-1`;
- missing, duplicate, conflicting, unopened, or unclosed episodes abstain;
- no event may alter another episode's state;
- output contains only finalized `(episode_id, ordered item_ids)` bundles.

## 3. Public-synthetic fixture

Generate deterministically from a committed seed:

- 24 clean episodes;
- 8 items per episode;
- a shared 64-item vocabulary, so identity alone cannot encode position;
- four content variants per item/position pairing;
- interleaved event delivery across episodes.

Fault cases are generated separately:

1. reversed and randomly shuffled delivery;
2. exact duplicate events;
3. close-before-items delivery;
4. one missing item;
5. duplicate position;
6. duplicate item at two positions;
7. conflicting duplicate `event_id`;
8. missing open or close;
9. cross-episode interleaving;
10. content-variant permutation.

No private AB memory or real episode is used.

## 4. Fixed-budget recall probe

For each clean episode, a deterministic content baseline returns one true seed
plus seven same-topic distractors at budget 8. The sidecar arm may replace the
page with the finalized ordered bundle only after the seed resolves to exactly
one finalized episode.

For an incomplete, conflicted, or ambiguous episode it must return the baseline
byte-for-byte. It may not enlarge the budget.

## 5. Admission gates

### Contract gate

- clean membership precision/recall/F1 = `1.0`;
- clean position accuracy = `1.0`;
- original, reversed, shuffled, duplicated, and close-first streams produce
  byte-identical finalized bundles;
- content permutation produces the same bundle identities and positions.

### Fail-closed gate

- every malformed episode is absent from finalized output;
- unrelated clean episodes remain byte-identical;
- malformed episode recall pages equal their baselines;
- no partial membership leaks.

### Recall gate

- sidecar set-recall@8 lift >= `+0.50` on eligible clean episodes;
- eligible episode regression count = `0`;
- output budget remains exactly 8;
- ambiguous seed-to-episode mappings abstain.

### Determinism gate

Two independent runs with the same fixture seed must emit byte-identical
aggregate reports. No wall clock, process randomness, network, database, or
environment value may affect generation or scoring.

## 6. Decision

- If all gates pass, R4 may design a default-off observation-only integration
  surface for review. R3 itself still does not authorize it.
- If contract or fail-closed gates fail, repair the reducer before any further
  experiment.
- If recall lift fails despite perfect reconstruction, stop the explicit
  scaffold direction.

## 7. Negative authority

R3 does not authorize changes to SQLite schemas, `MemoryRecord`, MCP tools,
memory writes, search order, telemetry, deployment, real-session capture,
training, or BioCortex.
