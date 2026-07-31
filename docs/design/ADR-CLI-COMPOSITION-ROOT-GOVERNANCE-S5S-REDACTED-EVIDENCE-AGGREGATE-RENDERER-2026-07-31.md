# ADR: CLI composition-root governance S5-S redacted-evidence aggregate renderer

## Status

Accepted on 2026-07-31.

## Context

`RetrievalOptInRedactedEvidenceAggregate` combined two responsibilities in
`main.rs`: constructing a redacted aggregate from two fixture-run files and
presenting the already-populated payload as JSON or text. S5-R established that
pure presentation can live in the existing private `cli::biocortex` module
without moving input custody or BioCortex authority.

## Options considered

1. Leave the command unchanged. This avoids a diff but retains presentation in
   the composition root.
2. Move the complete aggregate command. This removes more lines but also moves
   file loading, redaction summaries, schema decisions, and evidence custody.
3. Move only the populated-payload renderer. This is the smallest boundary and
   follows the proven S5-R seam.

## Decision

Choose option 3. `main.rs` builds the complete payload through
`build_biocortex_retrieval_opt_in_redacted_evidence_aggregate`. The private
`cli::biocortex` module owns
`run_biocortex_retrieval_opt_in_redacted_evidence_aggregate(payload, as_json)`.
Text presentation reads the same existing payload fields used to construct the
previous local summary values.

## Consequences

- Clap schema, dispatch, input paths, exact file errors, fixture summaries,
  redaction decisions, metadata, and payload construction remain in `main.rs`.
- No payload field, JSON output, text output, exit behavior, Store/Hub access,
  retrieval behavior, approval state, MCP surface, or runtime authority changes.
- The renderer can be verified independently with an ownership contract and an
  exact baseline/candidate CLI matrix.
- Further aggregation extraction is intentionally deferred; it requires a new
  ownership and authority review.
