# Trigger Recall Pre-Policy Hold Aio2 Audit Evidence

Date: 2026-06-23

Scope: docs-only follow-up evidence for merged mainline
`fbeebeb merge trigger pre-policy hold simulation candidate`.

This document fills the aio2 baseline acceptance audit gap recorded in:

- `2026-06-23-trigger-recall-pre-policy-hold-stage2-review.md`
- `2026-06-23-trigger-recall-pre-policy-hold-owner-merge-closeout.md`

It does not authorize deployment, installed-binary rollout, default
`memory_search` changes, production `enforce_hold`, non-Niche exposure, memory
writes, graph writes, semantic retrieval, or graph retrieval.

## Evidence Target

| Field | Value |
|---|---|
| mainline commit | `fbeebeb` |
| merged candidate commit | `2ceeef974066d382f69a0f2774ea08e452ca5252` |
| owner closeout | `MERGED-BY-OWNER-OVERRIDE-WITH-AIO2-AUDIT-GAP-RECORDED` |
| evidence node | `/Data/CascadeProjects/agent-bridge` |
| audit database | `/home/pallasting/.local/share/agent-bridge/state.db` |
| regression anchor | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |

## Command

Run from `/Data/CascadeProjects/agent-bridge` at `fbeebeb`:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result: passed with existing warnings only.

## Observed Metrics

| Metric | Observed |
|---|---:|
| active rows | 467 |
| trigger rows | 39 |
| projected rows | 38 |
| corpus cases | 14 |
| negative controls | 8 |
| baseline FTS R@1 | 0.714 |
| baseline FTS R@5 | 0.857 |
| baseline FTS R@10 | 0.857 |
| baseline FTS MRR | 0.786 |
| baseline shadow R@1 | 0.714 |
| baseline shadow R@5 | 0.857 |
| baseline shadow R@10 | 0.857 |
| baseline shadow MRR | 0.786 |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits before shadow gate | 21 |
| baseline false hits after shadow gate | 0 |
| false hits removed by shadow gate | 21 |

False-hit buckets:

| Bucket | Before | After | Removed |
|---|---:|---:|---:|
| unrelated | 3 | 0 | 3 |
| policy adversarial | 18 | 0 | 18 |

Held controls by reason:

| Reason | Count |
|---|---:|
| `creative_non_continuation_intent` | 2 |
| `frontend_dashboard_intent` | 2 |
| `health_dashboard_intent` | 1 |
| `write_bypass_intent` | 2 |

## Boundary Confirmation

The audit output reported:

- `read_only`: SELECT plus in-memory FTS only;
- no `memory_get`;
- no MCP `memory_search`;
- no writes;
- no reindex;
- `default_memory_search_unchanged=true`;
- `changes_default_memory_search_order=false`;
- `changes_production_retrieval=false`.

The previously missing Mac-side corpus key was present on this Aio2 `/Data`
node, so the audit completed and met the Stage-2 thresholds:

- true hits lost by shadow gate: `0`;
- positive cases held: `0`;
- baseline false hits after shadow gate: `0`.

## Decision Impact

This evidence closes the recorded aio2 audit gap for the merged `fbeebeb`
mainline state.

Still not authorized by this document:

- production `enforce_hold`;
- default `memory_search` behavior changes;
- deployment or installed-binary rollout;
- exposing the simulation outside `Tier::Niche`;
- memory or graph writes.
