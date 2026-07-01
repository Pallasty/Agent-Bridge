# BioCortex T6 Relevance-Lift Head Sample

Date: 2026-07-01
Scope: Agent-Bridge memory eval, read-only evidence

## Question

Does the current BioCortex side-signal reorder show measurable relevance lift on
a small high-importance self-retrieval sample, without exposing raw queries,
raw keys, memory content, or changing production retrieval order?

## Method

Tool: `memory_biocortex_relevance_lift_summary`

Parameters:

- `sample_size=8`
- `sort=by_importance`
- `limit=10`
- `or_terms=8`
- `include_related=true`
- `timeout_ms=120000`
- default `blend_alpha=0.8`
- default `coverage_threshold=0.8`

Safety contract reported by the tool:

- `read_only=true`
- `mutates_ab_memory=false`
- `writes_state=false`
- `changes_prod_retrieval_order=false`
- raw queries, raw keys, source content, samples, and side-signal raw output
  were not included in the summary surface.

## Result

Verdict: `no_lift`

Summary metrics:

| Metric | Value |
| --- | ---: |
| evaluated_count | 8 |
| source_found_count | 8 |
| improved | 0 |
| unchanged | 8 |
| worsened | 0 |
| order_changed_count | 5 |
| mrr_baseline | 1.000 |
| mrr_reordered | 1.000 |
| mrr_lift | 0.000 |

Recall:

| k | baseline | reordered | lift |
| ---: | ---: | ---: | ---: |
| 1 | 0.521 | 0.521 | 0.000 |
| 3 | 0.646 | 0.646 | 0.000 |
| 5 | 0.687 | 0.687 | 0.000 |
| 10 | 0.687 | 0.687 | 0.000 |

## Interpretation

This is useful negative evidence. The side-signal reorder changed candidate
order in 5 of 8 evaluated samples, but did not improve MRR or recall at any
reported cutoff. It also produced no regressions on this small head sample.

The correct read is:

- The redacted T6 relevance-lift surface is operational and preserves its
  privacy/read-only boundary.
- This head sample does not justify runtime search-order influence.
- Order movement alone is not relevance lift.
- A self-retrieval head sample is necessary-not-sufficient evidence; it is not a
  downstream recall corpus.

## Caveats

- Samples are the head of the chosen sort, not random.
- Query source is self-retrieval, derived from the target memory.
- The production reorder blend is evaluated locally only; it is never returned
  as live recall.
- This report does not approve `runtime_adapter_approved=true`, default search
  order mutation, schema/tokenizer/reindex work, graph/PageRank influence, or
  memory writes.

## Next Gate

For further BioCortex retrieval work, prefer explicit downstream query cases
with operator-supplied relevance labels. Keep this head-sample result as a
sanity check: before any runtime influence proposal, require nonzero lift on a
more realistic labeled corpus and a zero-regression review packet.
