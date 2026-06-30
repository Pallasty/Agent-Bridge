# Agent-Bridge Symbiosis Model-Card Summary

Date: 2026-06-30
Status: design memo, read-only archive summary, no runtime integration

## Decision

Agent-Bridge may borrow Symbiosis's compact "thinking model" shape as a
reviewable model/tool-card vocabulary: context, state, usage evidence, value
metrics, relationship hints, and revision history.

This memo does not import Symbiosis code, read generated model JSON, inspect
configs or API-key documents, register an MCP tool, write memory rows, write
graph edges, change retrieval order, select runtime models, or add a model
registry. It only records a possible review shape for later owner-gated work.

## Source Anchors

Agent-Bridge boundary documents:

- `CASCADE_PORTFOLIO_IDEA_ARCHIVE_READONLY_2026_06_29.md`
- `AB_SANITIZED_MEMORY_VOCABULARY_AUDIT_2026_06_29.md`
- `AB_PROJECTION_BUILDER_PATTERN_AUDIT_2026_06_30.md`
- `AB_PROPERTY_TEST_MOTIF_SAMPLER_2026_06_30.md`
- `BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_PACKET_2026_06_27.md`

Symbiosis read-only source slice:

- `Symbiosis/README.md`
- `Symbiosis/docs/UNIFIED_PROJECT_ROADMAP.md`
- `Symbiosis/src/core/thinking_model.py`
- `Symbiosis/src/core/model_manager.py`
- `Symbiosis/examples/thinking_model_demo.py`

The Symbiosis checkout is a dirty archive worktree. This lane intentionally did
not read `config/`, API endpoint docs, key-management docs, generated
`example_models/*.json`, or local runtime artifacts.

## Observed Symbiosis Shape

`ThinkingModel` combines:

- identity fields: id, name, description, creator, created timestamp;
- context: domain, scenario, requirements, constraints, metadata;
- state: active, evolving, stable, deprecated;
- usage statistics: views, references, successes, total attempts, last used,
  success rate, and usage history;
- value metrics: effectiveness, reliability, versatility, innovation, weighted
  overall score, and metric history;
- adaptation/evolution fields: adaptation score, version, parent id, child ids,
  and evolution history.

`ModelManager` provides a small management shell:

- create, get, and list models;
- establish symmetric relationships between model ids;
- find related models;
- choose a best active model for a context by combining context compatibility
  and value score;
- save models to JSON and expose aggregate stats;
- clean deprecated unused models.

The demo exercises the same loop: create contexts, create models, add
relationships, record usage, update value metrics, find a best model for a new
context, print stats, and save JSON.

The useful idea for Agent-Bridge is the card grammar, not the implementation.
The risky idea is automatic best-model selection: in AB it must remain advisory
until a separate review gate proves safety, regression behavior, and owner
intent.

## AB Translation

| Symbiosis concept | Agent-Bridge translation | Boundary |
|---|---|---|
| `ThinkingModel` | `model_card` or `tool_card` review artifact for an agent/tool/report surface | A card is evidence for review, not runtime authority. |
| `Context` | intended surfaces, trigger hints, input contract, constraints, and negative contexts | Hints must not silently alter retrieval, routing, or default tool exposure. |
| `ModelState` | review status such as draft, reviewable, active-doc, deprecated, rejected | Status is display metadata unless a later gate binds it to behavior. |
| usage statistics | observed evidence, verification commands, forum posts, commits, failures, recency | Counts are not proof of correctness without falsifiers. |
| value metrics | review metrics such as effectiveness, reliability, versatility, novelty, blast radius | Scores can prioritize review; they do not grant writes or execution. |
| adaptation score | fit assessment between context and card intent | Fit is advisory and must include negative controls before any ranking influence. |
| relationship network | related-card hints, source anchors, successor/predecessor links | Hints are not graph writes by default. |
| best-model matching | recommended card or surface for a context | Default-off. No automatic runtime selection in this memo. |
| evolution history | owner-reviewed revisions with provenance, tests, and rollback notes | No autonomous self-modification. |
| JSON persistence | possible fixture or index once a concrete consumer exists | Do not add a registry before repeated use proves need. |

## Proposed Review Shape

If a concrete consumer appears, start with a document or fixture shaped like:

```json
{
  "schema": "agent_bridge.model_card.review_shape.v0",
  "card_id": "agent_bridge.example.card",
  "source_kind": "tool|agent|report|memory_surface|archive_summary",
  "title": "...",
  "purpose": "...",
  "intended_surfaces": ["review", "forum", "handoff"],
  "non_goals": ["runtime_selection", "memory_write", "retrieval_ranking"],
  "input_contract": {
    "required_evidence": [],
    "accepted_contexts": [],
    "rejected_contexts": []
  },
  "output_contract": {
    "display_shapes": [],
    "forbidden_affordances": []
  },
  "selection_policy": {
    "advisory_only": true,
    "default_enabled": false,
    "may_select_runtime_model_now": false
  },
  "relationship_hints": [],
  "value_metrics": {
    "effectiveness": null,
    "reliability": null,
    "versatility": null,
    "novelty": null,
    "blast_radius": null
  },
  "safety": {
    "read_only": true,
    "may_write_memory_or_graph_edges": false,
    "changes_retrieval_order": false,
    "mcp_tool_registration": false,
    "executor_enabled": false
  },
  "evaluation": {
    "verification_commands": [],
    "negative_controls": [],
    "falsifiers": []
  },
  "provenance": {
    "source_anchors": [],
    "commits": [],
    "forum_posts": [],
    "owner": null,
    "reviewer": null
  },
  "revision_history": [],
  "review_status": "draft"
}
```

This shape mirrors AB's existing report/display packet habit: one selected
evidence packet can become a Markdown review artifact, dashboard card, forum
post, or handoff payload while keeping safety flags visible near the top.

## Existing AB Fit

- The BioCortex capability ledger already behaves like a capability card:
  static source, safety checks, review artifact, report packet, and display
  model.
- The projection-builder pattern supplies the card-to-display path and the rule
  that display readiness never grants execution authority.
- The sanitized memory vocabulary audit supplies the boundary for context,
  relationships, scores, and evolution language.
- The property-test motif sampler supplies the required negative controls:
  forbidden-field flips, redaction no-leak checks, deterministic fixtures, and
  no-authority invariants.

## Adoption Rules

1. Keep model/tool cards as docs or fixtures until a concrete reader exists.
2. Begin with one existing AB surface, not a generic registry.
3. Treat context matching as advisory review evidence only.
4. Treat relationship hints as proposed links only; graph writes require the
   normal preflight gates.
5. Treat value metrics as review metadata, not ranking authority.
6. Include at least one negative control for every card that claims read-only,
   no runtime selection, no graph write, no memory write, and no retrieval
   influence.
7. Add code only when the same card fields are consumed by at least one real
   report, board, handoff, or MCP response.
8. Do not read or ingest raw Symbiosis configs, generated models, API endpoint
   docs, key-management docs, caches, or local artifacts.

## Suggested Next Narrow Lane

If this direction becomes active, the first implementation should be a tiny
fixture-backed `model_card` for one already-static AB surface, most likely the
BioCortex capability ledger. The fixture should prove:

- stable serialization;
- accepted and rejected card variants;
- a forbidden `may_select_runtime_model_now=true` flip rejects;
- a forbidden `may_write_memory_or_graph_edges=true` flip rejects;
- no raw memory/query/key/content fields appear in the display projection.

Until that concrete consumer exists, this memo is enough.

## Non-Claims

This memo does not:

- create a model-card registry;
- add a Rust module, test, fixture, or MCP registration;
- call BioCortex, Symbiosis, Palace, daemon, network, runtime, socket, watcher,
  or executor APIs;
- write memories, work memories, graph edges, audit rows, approval records, or
  board state;
- change retrieval, bootstrap, candidate expansion, ranking, or tool exposure;
- approve context-based model routing;
- approve autonomous adaptation or self-modification.

It only records how to translate Symbiosis's compact thinking-model grammar
into Agent-Bridge's review-first design language.
