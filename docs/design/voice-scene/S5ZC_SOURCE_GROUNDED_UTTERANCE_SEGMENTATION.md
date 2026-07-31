# S5ZC source-grounded utterance segmentation

S5ZC resolves the two S5ZB attributed-dialogue blockers without executing TTS.
A line containing one complete Chinese or ASCII quote pair is split into a
narration prefix and a dialogue body. The narration uses Vivian, the dialogue
retains the source event's accepted character voice, and both derived events
retain the original event ID plus exact source character spans.

The only spoken-text normalization is explicit and auditable: an attribution
prefix ending in a colon is rendered with a full stop. Its `source_text` and
exact colon-bearing span remain in the receipt. Missing, unbalanced, nested, or
multiple quote pairs remain review-blocked instead of being guessed.

On `story_s1.md`, five S5ZB events become seven voice segments. The two quoted
lines split into Vivian attribution plus Dylan or Serena dialogue. Every stored
`source_text` matches the exact source slice, the review queue is empty, and the
plan becomes eligible for a separately bounded first-chapter Qwen render. This
stage itself loads no model, emits no audio, and does not register `/story`.
