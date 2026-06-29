# Agent-Bridge Sanitized Memory Vocabulary Audit

Date: 2026-06-29
Status: design memo, read-only vocabulary audit

## Decision

Agent-Bridge may borrow memory-review vocabulary from the portfolio idea
archives only after translating it into existing AB primitives: memory records,
metadata, graph edges, evidence packets, redacted summaries, review gates, and
display projections.

This memo does not import archive data, add runtime code, create a new MCP tool,
write memory rows, write graph edges, or change retrieval order. It is a
sanitized glossary and review checklist for later design work.

## Source Anchors

This audit is intentionally based on already-landed Agent-Bridge docs rather
than another pass through raw archive trees:

- `CASCADE_PORTFOLIO_IDEA_ARCHIVE_READONLY_2026_06_29.md`
- `MEMORY_AUTHORIZATION_CONTRACTS_2026_06_25.md`
- `MEMORY_CONTINUITY_T1_METADATA_2026_06_19.md`
- `MEMORY_CONTINUITY_T5_T6_EVIDENCE_SURFACES_2026_06_19.md`
- `MEMORY_CONTINUITY_T6_INFLUENCE_GATE_2026_06_19.md`
- `DESIGN-memory-search-ranking-2026-05-23.md`
- `CONTROLLED_RECURSIVE_SELF_IMPROVEMENT_FOR_AGENT_BRIDGE_2026_06_21.md`

The portfolio memo already marked AIMemoryPalace_v2, QMSs, QNNs, TCT/TCF/TTE,
Genesis, Symbiosis, and `symbiosis_architecture` as idea archives only. This
audit preserves that boundary.

## Vocabulary Translation

| Archive wording | Allowed AB translation | Boundary |
|---|---|---|
| memory palace / memory unit | `MemoryRecord` or memory row with key, kind, content, tags, scope, related keys, and continuity metadata | No raw archive row import. New records still require normal `memory_save` authority and scope policy. |
| context-bearing memory | continuity metadata, retrieval trigger hint, scope, tags, or review packet metadata | Metadata is not automatically indexed recall. `retrieval_trigger` stays descriptive unless a later explicit projection/index gate lands. |
| association | proposed graph edge, related-key hint, or review candidate | A proposal is not a write. Edge writes require the existing graph-hygiene/pre-write gates and caps. |
| relationship strength | bounded score, edge weight, corroboration count, or relevance metric with source and range | Scores are evidence fields, not authority. They must not silently become ranking priors. |
| resonance | relevance signal, similarity score, coactivation evidence, or advisory side signal | Do not use "resonance" as a capability claim. Translate it to a measured signal and cite the metric. |
| value / priority | `importance`, actionability, blast radius, or review priority | Priority can queue human review; it does not grant mutation rights. |
| conflict / consistency | blocker, falsifier, regression anchor, negative-control check, or review caveat | A conflict finding should fail closed or request review, not auto-repair state. |
| projection | display packet, report, forum post, dashboard card, handoff, or operator view over the same evidence packet | Projection must not mutate the underlying evidence, memory, graph, or retrieval order. |
| evolution | owner-reviewed schema, policy, or document change with tests and rollback | Not autonomous self-modification. Controlled-RSI rules still apply. |
| application | explicit runtime surface, report surface, or action executor | Runtime behavior needs separate approval, default-off posture, preflight evidence, and rollback. |

## Forbidden Vocabulary Claims

The following words are allowed only as quoted archive labels or historical
context, not as Agent-Bridge capability claims:

- consciousness
- quantum life
- autonomous cognition
- autonomous objective discovery
- self-evolving memory
- runtime authority
- memory write authority
- retrieval-order mutation

If a future document uses one of these words, it must either translate the word
into an AB primitive in the same paragraph or mark it as out of scope.

## Allowed Source Use

Allowed:

- borrow concept names after translation into AB primitives;
- build review checklists, diagrams, or design prompts from sanitized summaries;
- compare archive patterns with existing AB evidence-surface and gate patterns;
- cite the portfolio memo as the boundary source.

Not allowed:

- auto-ingest archive files into Agent-Bridge memory;
- import raw conversations, generated memory JSON, configs, API lists, keys,
  caches, plots, checkpoints, or local runtime artifacts;
- treat an archive project as a live runtime dependency;
- wire archive code into AB, BioCortex, Onsen, or Palace execution paths;
- use archive terminology to bypass review, redaction, owner approval, or
  runtime feature gates.

## Review Checklist

Before any future design borrows archive memory language, answer yes to all:

1. Is the source a sanitized memo or reviewed excerpt rather than raw archive
   content?
2. Is every archive term translated into an existing AB primitive?
3. Does the artifact state whether it is a record, metadata field, graph edge,
   evidence packet, projection, review gate, or runtime surface?
4. Are raw query/key/content/case rows excluded when the surface is meant to be
   redacted?
5. Does the artifact preserve `may_write_memory_or_graph_edges=false` and
   `changes_search_order=false` unless a later explicit authority says
   otherwise?
6. Is there a falsifier, validation command, regression anchor, or owner-review
   gate before implementation?
7. Does it avoid implying consciousness, autonomous cognition, runtime
   authority, or self-modification?

## Useful Next Lanes

1. Add a tiny glossary fixture only if a future reviewer needs machine-checkable
   terms. Do not do that before a concrete consumer appears.
2. Compare projection-system language with existing AB display packets and
   forum/report surfaces.
3. Mine property-test motifs from TCT/TCF/TTE as abstract test patterns, not
   imported code.

## Current Non-Claims

This memo does not:

- run BioCortex;
- call `memory_search`;
- write memories, work memories, graph edges, approval records, or audit rows;
- create a new MCP registration;
- alter Codex tool profiles;
- change default retrieval, bootstrap, candidate expansion, or ranking;
- approve runtime influence.

It only makes the archive-to-Agent-Bridge language boundary explicit.
