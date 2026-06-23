# Main Recall Case #2 Tool-Surface Positive Controls

Date: 2026-06-23
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge`
Base: `17660e9` (`feat(memory): add T6 shadow executor invocation report`)
Scope: eval-only diagnostic/probe

## Why

The negative-control slice showed that the case #2 tool-surface projection does
not overmatch generic tool-use, latency, MCP diagnostic, git/worktree, or
`memory_search` quality queries. This slice tests the other side:

> Does the projection generalize within the intended tool-surface policy family?

This still does not touch production `memory_search`.

## Change

`crates/bridge/examples/recall_eval.rs` now prints:

```text
## Case #2 tool-surface positive controls
```

The probe adds:

- 11 positive controls covering Chinese paraphrases, English tool-surface /
  taxonomy / re-tier / delete wording, and near-positive profile/tier policy
  wording anchored by `tool surface`;
- `toolproj_acc_strict_durable`: a stricter scratch-only accepted mode that
  requires `projtoolsurface` plus at least three additional shared policy terms;
- policy-cluster accounting for:
  - `reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618`;
  - `goal_b_surface_growth_gate_engine_finding_20260621`;
- candidate hygiene tightening: durable tool-surface projection excludes
  `work_memory_`, `snapshot_`, `alert_`, and `skill:` keys.

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo run -p ab-bridge --example recall_eval
cargo check -p ab-bridge --all-targets
```

Observed positive-control summary:

```text
controls=11 durable_hits=11 strict_hits=11 strict_cluster_hits=11 strict_empty=0
```

Representative strict hits:

| control | strict reference rank | strict cluster rank | read |
|---|---:|---:|---|
| `zh_classify_contract_retier` | 1 | 1 | Chinese classify/contract/delete/re-tier paraphrase |
| `zh_surface_taxonomy_converge` | 2 | 1 | mixed Chinese/English surface/taxonomy/contraction/delete |
| `en_tool_surface_too_large` | 3 | 1 | English surface/taxonomy/delete/re-tier/profile wording |
| `mcp_surface_allowlist` | 1 | 1 | near-positive MCP tool-surface allowlist policy |
| `profile_tier_allowlist_policy` | 1 | 1 | near-positive profile/tier policy with tool-surface anchor |

The standard main hard-tier runtime gate remains unchanged and separately
reported:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.000 semantic=0.125
```

## Read

The projection now passes the first positive-control gate:

- all 11 positive controls pass strict durable acceptance;
- the designated taxonomy reference is visible for all positive controls;
- the policy cluster is rank 1 for all positive controls;
- `skill:` rows are now excluded from the durable candidate view after one
  raw accepted distractor appeared in the baseline case #2 accepted set.

The result is still not runtime-ready:

- the designated reference is not consistently rank 1;
- `goal_b_surface_growth_gate_engine_finding_20260621`,
  `mcp_codex_native_overlap_surface_narrowed_deployed_20260617`, and
  `tool_diagnostics_plan_load_lookup_miss_20260619` remain nonvolatile
  distractors inside the strict set;
- this probe is still case-family-specific and hand-curated.

So the current conclusion is:

```text
visibility and family generalization: passed
candidate hygiene: partially improved
rank/specificity: still open
runtime authorization: no
```

Concurrent board review #3929 correctly notes that the standing hard-tier
runtime anchor currently reads the live Mac store, so the baseline can drift as
agents add or access memories. This report uses the live-store output only as
case-family diagnostic evidence, not as a production-lift measurement. Any
future runtime proposal should first freeze a baseline DB snapshot through the
existing `AB_BASELINE_DB` path and compare before/after against the same store
content.

## Next Gate

Recommended next slice before runtime design:

```text
main-recall-frozen-baseline-anchor-v1
```

That slice should pin the main hard-tier runtime gate to a frozen DB snapshot so
future retrieval proposals can distinguish real lift from live-store drift.

After that, continue with:

```text
main-recall-case2-tool-surface-rank-adjudication-v1
```

That slice should content-read and classify the recurring nonvolatile
distractors:

1. `goal_b_surface_growth_gate_engine_finding_20260621`: likely same-policy
   cluster; decide whether it is also-correct, fresher, or overly broad.
2. `mcp_codex_native_overlap_surface_narrowed_deployed_20260617`: likely
   adjacent tool-surface overlap/deployment policy; decide whether it should
   stay in cluster or be demoted for this query family.
3. `tool_diagnostics_plan_load_lookup_miss_20260619`: likely a diagnostic
   distractor; decide whether query/candidate specificity needs a stricter
   taxonomy/contraction/delete requirement.

Only after rank adjudication should a runtime candidate-expansion design be
written.

## Boundary

This slice does not change production `memory_search`, tokenizer/schema/reindex,
ranking, graph expansion, semantic retrieval, MCP tools, memory rows, or deploy
behavior.
