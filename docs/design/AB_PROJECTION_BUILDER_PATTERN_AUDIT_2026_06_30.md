# Agent-Bridge Projection Builder Pattern Audit

Date: 2026-06-30
Status: design memo, no runtime or MCP change

## Decision

Agent-Bridge should treat "projection builder" as a house pattern for turning
one reviewed evidence packet into several read-only presentation shapes:
Markdown report, report packet, display model, dashboard card, forum post body,
or handoff payload. The projection may summarize, group, badge, tone, and route
evidence, but it must not re-read unsafe sources, mutate store state, grant
runtime authority, or change retrieval behavior.

This memo records the pattern. It does not add a Rust abstraction, register an
MCP tool, write memory or graph edges, or wire any archive project into
Agent-Bridge.

## Source Anchors

This audit uses the sanitized portfolio boundary plus existing Agent-Bridge
projection surfaces:

- `CASCADE_PORTFOLIO_IDEA_ARCHIVE_READONLY_2026_06_29.md`
- `AB_SANITIZED_MEMORY_VOCABULARY_AUDIT_2026_06_29.md`
- `LIVE_SEMANTIC_WORLD_RUNTIME_READONLY_BRIDGE_REPORT_PACKET_2026_06_07.md`
- `LIVE_SEMANTIC_WORLD_RUNTIME_READONLY_BRIDGE_DISPLAY_MODEL_2026_06_07.md`
- `BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_2026_06_27.md`
- `BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_PACKET_2026_06_27.md`
- `BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_DRY_RUN_2026_06_29.md`
- `GOAL_C_REPORT_FIRST_UTILITY_SURFACE_2026_06_21.md`
- `crates/bridge/src/lswr_snapshot_report_packet.rs`
- `crates/bridge/src/lswr_snapshot_display.rs`
- `crates/bridge/src/biocortex_capability_ledger.rs`
- `crates/bridge/src/biocortex_composed_limit_cycle.rs`
- `crates/bridge/src/session_handoff.rs`

The TCF projection-system idea is used only through the sanitized portfolio
memo: one evidence state can have semantic, visual, structural, or interactive
views. No raw TCF files are imported or re-read here.

## Observed Existing Shape

The strongest existing examples already follow a shared chain:

```text
source evidence -> consumer/summary -> review artifact -> report packet -> display model
```

Examples:

- LSWR read-only bridge packages a consumer summary plus Markdown report into
  `agent_bridge.lswr.readonly_bridge_report_packet.v0`, then derives
  `agent_bridge.lswr.readonly_bridge_display_model.v0` with status, badges,
  metrics, gates, readback groups, guidance, and report Markdown.
- BioCortex capability ledger parses a static ledger into a consumer summary,
  renders a Markdown review artifact, wraps both in a report packet, then builds
  a display model for board/report/handoff readers.
- BioCortex C1 composed-limit-cycle repeats the same pattern with additional
  domain fields for caveats, ablation controls, and scope non-claims.
- Goal C's report-first utility surface is the same idea at the document layer:
  compose existing evidence into a standing report before adding a new MCP tool.
- `session_handoff` is a simpler projection over git state, todos, handoff
  memories, open questions, and conversation snippets. It is useful, but it is
  not a full safety-gated display model because it may include raw memory
  content and snippets.

## Required Projection Invariants

Future projection builders should preserve these invariants unless a later
owner-reviewed design explicitly narrows or extends them:

1. **Explicit input**: the builder consumes an already selected summary, packet,
   or operator-supplied fixture. It does not crawl arbitrary paths or live
   runtime state.
2. **Deterministic output**: same input produces the same packet/model, including
   stable schema strings and stable pretty-JSON fixtures when fixtures exist.
3. **Schema lineage**: output carries its own schema plus source/summary/report
   schemas so downstream surfaces can reject mismatches before reading nested
   data.
4. **Top-level safety**: read-only, mutation, runtime, retrieval-order, memory,
   graph-edge, MCP-registration, and executor flags appear near the top of the
   packet/model, not only deep inside a nested summary.
5. **No authority by projection**: display readiness means "safe to show", not
   "safe to execute". Projection never grants runtime admission, memory writes,
   graph writes, retrieval influence, or candidate expansion.
6. **Rejected is visible**: unsafe, stale, mismatched, or rejected packets become
   rejected display models with reasons. The builder must not silently hide or
   coerce failures into success.
7. **No action affordance**: display models can include guidance and next review
   gates, but not patch/apply/invoke buttons or executable plans.
8. **Redaction stays load-bearing**: if the source is a redacted evidence
   surface, the projection must not re-include raw queries, raw keys, content,
   case rows, source packets, or side-signal errors.
9. **Allowed/forbidden surfaces are named**: display models should say where
   they may go, such as report, forum post, dashboard card, or handoff packet,
   and where they may not go, such as memory writer, graph mutator, executor,
   retrieval ranker, or runtime gate.
10. **Tests include negative controls**: accepted fixture, rejected fixture,
    mutating safety flag, runtime-decision wording, raw-payload leakage, and
    stable serialization should be tested before any tool or dashboard consumes
    the model.

## Common Field Grammar

A projection builder does not need a shared Rust trait yet, but new surfaces
should use a familiar grammar:

| Shape | Purpose | Expected fields |
|---|---|---|
| `consumer_summary` | Domain-specific validation over source evidence | `schema`, input provenance, `verdict`, `read_only_confirmed`, `safety`, checks, guidance |
| `review_artifact` | Human-readable Markdown | source schema, verdict, safety, failed checks, guidance, boundary |
| `report_packet` | Stable machine payload | packet schema, source schemas, top-level safety, summary, `report_markdown` |
| `display_model` | Board/dashboard/handoff-ready view | display schema, packet schema, title, status/tone, safety, badges, metrics, rows/groups, guidance, report Markdown |

Status/tone should stay small and boring:

```text
accepted -> Ready for read-only display / success
needs_review -> Needs review / warning
rejected or mismatch -> Rejected / danger
```

## When To Abstract In Code

Do not add a generic projection framework just because several modules look
similar. The current duplication is still useful because each domain has
different safety fields and negative controls.

Consider a small shared helper only when at least three new projection builders
repeat the same low-level mechanics and the helper can stay domain-neutral:

- `DisplayStatus` construction from accepted/needs-review/rejected;
- badge and metric constructors;
- stable bool text and one-line clipping helpers;
- common forbidden-surface lists;
- pretty-JSON fixture assertion helpers.

Do not abstract:

- domain safety structs;
- acceptance gates;
- redaction checks;
- runtime authority decisions;
- review wording that carries owner-specific constraints.

## Applying This To Future Archive Ideas

The sanitized TCF projection idea maps cleanly to AB only as:

```text
evidence packet -> presentation projection
```

It does not justify:

- importing archive code;
- generating new hidden state;
- adding an interactive runtime surface;
- treating a projection as a memory write, graph edge, or rank signal.

The next useful implementation lane, if a concrete consumer appears, is a tiny
fixture-backed display model for one existing report that lacks a stable
dashboard/handoff projection. Until then, this memo is enough: it names the
pattern and prevents future projection work from drifting into authority.

## Non-Claims

This memo does not:

- create a new MCP registration;
- alter tool profiles;
- call BioCortex or LSWR runtime code;
- read raw archive files;
- write memories, graph edges, audit rows, or approval records;
- change retrieval, bootstrap, candidate expansion, or ranking;
- approve runtime influence or executor enablement.

It only turns an observed Agent-Bridge practice into a reusable design
constraint.
