# Memory Continuity T0 Baseline (2026-06-19)

This note records the baseline constraint for the AB memory-continuity branch
after review reconciliation with thread #115.

T0 is observational. It must not add a new MCP tool surface or influence memory
retrieval order. The current source of truth for recall-quality measurement is
the drift-free held-out harness already landed on `origin/master`:

```bash
AGENT_BRIDGE_ONNX_MODEL=para-ml cargo run -p ab-bridge --example recall_eval
```

Use historical query telemetry only as operational telemetry. It mixes multiple
binary versions, query distributions, and corpus states, so its hit rate is not
a trustworthy current-quality recall metric. In particular, logged "returned at
least one row" is not the same as "returned the intended memory".

## Baseline Observations

The fixed held-out paraphrase harness reported the following starting point on
the live store:

- `fts`: R@1 0.188, R@5 0.500, R@10 0.625, MRR 0.309
- `hybrid`: R@1 0.062, R@5 0.188, R@10 0.438, MRR 0.146
- `semantic`: R@1 0.000, R@5 0.062, R@10 0.125, MRR 0.023

Methodological conclusion:

- FTS is currently strongest on the held-out set, but still misses hard
  paraphrase cases.
- Hybrid can be worse than FTS when graph expansion crowds out correct FTS
  hits.
- Semantic ranking needs real held-out lift before it can justify influence.

## Merge Boundary

Earlier branch drafts added a `memory_continuity_baseline` MCP tool. That tool
surface was removed during review reconciliation because master already has the
drift-free `recall_eval` harness and existing stats surfaces. Keeping T0
surface-free reduces tool bloat and avoids presenting historical log aggregates
as current recall quality.

T1-T7 may build on this baseline, but any claim of retrieval improvement must
compare against the fixed held-out harness or a later documented successor.

## Follow-Up

- Add section-level bootstrap token telemetry before tightening T2 budgets.
- Expand the held-out corpus with multiple acceptable target keys for cases
  where near-duplicate memories are also valid.
- Use the same harness before and after any future ranking, suppression, or
  BioCortex influence experiment.
