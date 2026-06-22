# Goal C U Follow-Up - Aio2 Graph Hygiene Preflight

Date: 2026-06-21

Host: Linux/Aio2

Scope: read-only memory graph hygiene preflight after
`docs/reports/goal-c-u/2026-06-21-aio2.md` and
`docs/reports/goal-c-u/2026-06-21-aio2-null-fts-hygiene.md`.

Verdict: `actionable` for explicit `related_keys` materialization dry-run and
orphan inventory review only.

This preflight did not write graph edges, mutate memory rows, change retrieval
ranking, approve PageRank or centrality as a live ranking prior, add an MCP
surface, approve runtime candidate expansion, or authorize an executor.

## Source Anchors

| Anchor | Value |
|---|---|
| repo worktree | `/Data/CascadeProjects/agent-bridge-goal-c-u-refresh-aio2-20260621` |
| source commit | `5662f1d45f89b2ea46850a18e50bec8b910d2fc1` |
| source subject | `docs: record aio2 null fts hygiene` |
| deployed binary | `/home/pallasting/.local/bin/agent-bridge.real` |
| deployed sha256 | `61c3df483889fe5c997b168e649b14dee58d79fdb1cc89a3020a751e73757653` |
| report timestamp | `2026-06-21T17:17:08Z` |

## Board And Runtime Anchors

Thread #120 remained the controlling Goal C board thread.

Consumed board updates:

- `#3775`: Aio2 `U` report landed.
- `#3778`: BioCortex S123 held-out falsifier spec landed separately; it did
  not approve an executor.
- `#3779`: Aio2 null FTS hygiene pass was reported.
- `#3782`: correction and final null FTS landing update.

Board update `#3781` is intentionally superseded by `#3782` because it named an
old commit and implied manual backfill/SIGTERM actions that did not happen.

Fresh runtime state during this preflight:

- lifecycle state: `ready`;
- readiness state: `ready`;
- daemon HTTP health: `ok`;
- Palace health: `ok`;
- scoped failing tool count: `0`;
- active `memories.fts_content IS NULL`: `0`;
- current `.real` MCP server count in `doctor`: `4`;
- `doctor`: `7 ok / 2 warn / 0 fail`;
- remaining `doctor` warnings were the missing `ab-system-control` helper
  checks.

## Topology Read

The broad `local_plus_global` topology still shows too much disconnected graph
mass for PageRank or centrality to become a live ranking prior.

| Metric | `local_plus_global` | `local_only` |
|---|---:|---:|
| non-skill active total | 479 | 163 |
| orphan count | 300 | 27 |
| orphan fraction | 0.626 | 0.166 |
| P4 evolved coverage | 143 | 115 |
| P4 evolved fraction | 0.299 | 0.706 |
| top hub degree | 22 | 21 |
| top hub fraction | 0.046 | 0.129 |
| PageRank readiness | `needs_graph_hygiene_before_rank_prior` | `observe_then_bound_centrality_boost` |

Interpretation:

- The AB-local graph is not the main problem. Its orphan fraction is high enough
  to keep observing, but not high enough to explain the broad PageRank block.
- The broad graph problem is mostly scope mixing plus global or unscoped memory
  pressure.
- Centrality can remain diagnostic, but it should not affect production
  retrieval order until the broad orphan pressure is bounded.

Palace graph health in the lifecycle digest was consistent with this read:

| Metric | Value |
|---|---:|
| nodes | 500 |
| edges | 772 |
| orphan nodes | 269 |
| connected ratio | 0.462 |
| explicit edges | 706 |
| coactivation edges | 66 |
| fresh nodes | 258 |
| stale nodes | 2 |

## Orphan Pressure

The broad orphan set is dominated by global/unscoped, auto-curated, implicit
rows rather than by the current AB project scope.

Approximate SQL cross-check for the broad selected set:

| Metric | Value |
|---|---:|
| selected rows | 478 |
| orphan rows | 300 |
| orphan fraction | 0.628 |
| global/unscoped orphans | 278 |
| AB-scoped orphans | 22 |

Broad orphan kinds:

| Kind | Count |
|---|---:|
| `todo` | 124 |
| `lesson` | 93 |
| `decision` | 61 |
| `context` | 11 |
| `session_handoff` | 6 |
| `alert` | 3 |
| `architecture` | 1 |
| `evidence` | 1 |

Top orphan tags:

| Tag | Count |
|---|---:|
| `auto_curated` | 268 |
| `implicit` | 259 |
| `unverified_identifier` | 54 |
| `agent-bridge` | 12 |
| `biocortex` | 9 |
| continuity-related tags | 8 |
| `memory` | 7 |
| `t6` | 7 |

This means a broad "link all orphans" strategy would mostly improve the graph
score by clustering noisy generated rows. That would make the topology look
better while weakening the semantic value of graph centrality.

## Explicit Related Keys Preflight

`memory_related_keys_preflight` was the highest-precision first write candidate,
but the expected orphan reduction is limited.

| Metric | Value |
|---|---:|
| visible total | 479 |
| current edge pairs | 324 |
| current orphans | 300 |
| safe candidate pairs | 140 |
| candidate sources | 86 |
| candidate targets | 94 |
| orphan candidate nodes | 20 |
| projected orphans after candidates | 280 |
| projected orphans reduced | 20 |

Candidate bucket summary:

| Bucket | Pairs | Sources |
|---|---:|---:|
| `safe_candidate` | 140 | 86 |
| `already_has_edge` | 103 | 66 |
| `target_scope_filtered` | 102 | 40 |
| `target_missing` | 57 | 33 |
| `cross_scope` | 7 | n/a |
| `duplicate_candidate` | 2 | n/a |
| `target_excluded_kind` | 5 | n/a |

Top safe kind-pairs:

| Pair | Count |
|---|---:|
| `decision -> decision` | 52 |
| `session_handoff -> session_handoff` | 13 |
| `lesson -> decision` | 10 |
| `decision -> lesson` | 8 |
| `context -> decision` | 7 |

Interpretation:

- Explicit `related_keys` materialization is appropriate as the first dry-run
  implementation target because it uses author-supplied structure.
- It should be capped and reported before any write because it only reduces 20
  orphan nodes in this broad view.
- The `target_missing` and `target_scope_filtered` counts show that stale
  related-key cleanup and scope normalization may matter as much as edge
  insertion.

## Automatic Orphan Candidate Read

`memory_orphan_candidates` showed that a broad automatic orphan linker would
find candidates too easily:

| Metric | Value |
|---|---:|
| examined | 239 |
| eligible orphans | 80 |
| would link | 80 |
| skipped low score | 0 |
| skipped no candidates | 0 |
| skipped blacklisted orphan | 1 |
| skipped blacklisted kind | 0 |

The sampled links were dominated by `curated_implicit_*` rows with high
confidence from `tag_overlap+same_prefix`.

Interpretation:

- This is useful as a review inventory.
- It is not a good first write path.
- Using it before curation would risk manufacturing low-value cliques from
  generated memories.

## Recommended Next Stage

### GHP-1: Explicit Related Keys Dry-Run

Add or run a dry-run-only report path that materializes no more than a small,
reviewable batch of explicit `related_keys` pairs.

Required constraints:

- read-only by default;
- same-scope or explicitly scope-compatible only;
- exclude `work_memory`, `snapshot`, and TTL-tagged rows;
- exclude generated-noise tags such as `auto_curated`, `implicit`, and
  `unverified_identifier` for the first pass;
- cap the first review packet at 20 pairs;
- include source key, target key, source scope, target scope, existing edge
  state, proposed edge type, and reason;
- require SQLite backup and `PRAGMA quick_check` before any later write mode;
- re-run topology after any write-mode experiment.

### GHP-2: Auto-Curated Orphan Inventory

Treat auto-curated/implicit orphan clusters as an inventory problem before they
become graph-ranking signal.

Possible outcomes for each cluster:

- archive or de-prioritize generated summaries that add no durable retrieval
  value;
- attach a small number of high-value summaries to canonical decisions;
- keep independent if the row is genuinely useful but intentionally unlinked;
- leave untouched when the value is unclear.

### GHP-3: Missing Target And Scope Cleanup

Produce a report-only pass for missing and scope-filtered `related_keys`.

Review questions:

- Does the referenced key still exist under a renamed key?
- Is the source memory scoped incorrectly?
- Is the target global by design, or should it be project-scoped?
- Should the stale `related_keys` entry be removed or replaced?

## Promotion Gate

Do not promote centrality, PageRank, or graph priors into live ranking until all
of the following are true:

- local-plus-global orphan fraction is materially lower after bounded,
  explainable hygiene;
- AB-local topology remains stable or improves;
- auto-curated/implicit rows no longer dominate the broad orphan set;
- related-key stale references have a cleanup report;
- offline graph expansion improves held-out recall without relying on noisy
  generated clusters;
- rollback is a simple edge-delete or backup restore operation.

## Non-Authorizations

This report does not authorize:

- PageRank or centrality in production retrieval ranking;
- live candidate-set expansion;
- automatic orphan linking;
- generated-memory clique formation;
- graph edge writes;
- memory row rewrites;
- new MCP tools;
- approval-gated executors;
- editor or agent client restarts.
