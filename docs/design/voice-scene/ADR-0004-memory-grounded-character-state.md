# ADR-0004: S3 character state is cursor-bounded and append-only

- Status: accepted for S3
- Date: 2026-07-29
- Exit state: `character_interaction_text_grounded`

## Three ledgers

S3 separates:

- `canon_ledger`: source-grounded events on `branch_canonical`;
- `character_knowledge_ledger`: what a named character learned and from which
  canon events;
- `interaction_ledger`: listener/character interactions on their explicit
  canonical or simulation branch.

Each ledger is append-only JSONL. Replaying the exact event ID and content is a
no-op. Reusing an event ID with different content is a hard conflict. Canon
events require a source locator and digest. A simulation interaction may never
target the canonical branch.

## Knowledge boundary

`/story ask` is text-first. Retrieval is limited by both:

1. the current playback cursor; and
2. explicit `known_by` character visibility.

The deterministic S3 reference implementation returns an evidence extract, not
an unconstrained generated answer. When no visible evidence supports the
question it returns a fixed insufficient-knowledge response.

Any later generative adapter must pass the spoiler falsifier. A candidate that
contains an unavailable future fact is replaced by the safe response. This
falsifier is intentionally conservative and does not claim semantic completeness.

## Psychological state

A psychological profile is always `claim_kind=inference`. It carries evidence,
counter-evidence, confidence, and bounded `state_delta`. Future evidence is
rejected. No psychological hypothesis may be stored as source truth.

## AB memory and resume

S3 produces a deterministic character-state snapshot suitable for explicit AB
memory persistence. The snapshot plus append-only interaction log reconstructs
the playback cursor, ledger counts, active branch, profiles, and interaction
history.

The implementation's write posture is
`proposal_only_owner_review_required`: it does not silently ingest story facts
or simulations into global AB memory. Project evidence may be persisted only
through an explicit owning workflow.

## Non-goals

S3 does not provide realtime voice, microphone capture, unconstrained roleplay,
production-grade semantic retrieval, automatic canon editing, or omniscient
character narration.
