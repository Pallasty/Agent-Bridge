# BioCortex Retrieval Review Packet

Date: 2026-06-10

## Decision Status

Human review decision: approved by user on 2026-06-10.

Runtime retrieval mutation remains forbidden:

```json
{"runtime_adapter_approved": false}
```

This packet summarizes the evidence needed before deciding whether to open a
separate runtime-boundary design for BioCortex retrieval influence.

## Metric Evidence

| corpus | queries | candidates/query | policy | baseline MRR | blended MRR | MRR delta | regressions | status |
|---|---:|---:|---|---:|---:|---:|---:|---|
| current | 35 | 5 | `candidate-strong` | 0.88095 | 0.92381 | +0.04286 | 0 | pass |
| easy holdout | 33 | 5 | `candidate-strong` | 0.98485 | 1.00000 | +0.01515 | 0 | fail due ceiling |
| hard holdout | 36 | 5 | `candidate-strong` | 0.94444 | 0.98611 | +0.04167 | 0 | pass |

The easy holdout is retained as a ceiling-effect finding, not as a failed
side-signal quality claim.

## Latency Evidence

Side-signal generation was measured locally by running the BioCortex example
against each corpus and writing JSONL to `/tmp`.

| corpus | queries | side rows | wall ms | ms/query |
|---|---:|---:|---:|---:|
| current | 35 | 175 | 101.477 | 2.899 |
| easy holdout | 33 | 165 | 48.032 | 1.456 |
| hard holdout | 36 | 180 | 48.323 | 1.342 |

These are offline benchmark timings only. Online latency must be measured again
if a runtime design is ever proposed.

## Current Corpus Review

Remaining expected-key failures after `candidate-strong`:

| query | expected | blended rank | blended top | review note |
|---|---|---:|---|---|
| `q_shadow_digest` | `decision_shadow_only` | 2 | `seed_legacy` | Adjacent governance concepts; side signal still overweights Seed legacy language. |
| `q_side_signal_schema` | `side_signal_schema` | 2 | `retrieval_benchmark` | Winner is related but broader than the schema-specific answer. |
| `q_disk_space` | `disk_space` | 3 | `gate_thresholds` | The query mentions implementation issue; candidate terms still favor gate language. |
| `q_side_signal_future` | `side_signal_future` | 2 | `plan_retrieval_gate` | Related planning concept beats the generator-specific answer. |
| `q_open_loop_boundary` | `open_loop_boundary` | 2 | `substrate_schema` | Adjacent substrate concepts remain close. |

Winner changes:

| query | baseline top | blended top | verdict |
|---|---|---|---|
| `q_side_signal_schema` | `embedding_gate` | `retrieval_benchmark` | Better than baseline, still not expected. |
| `q_gate_thresholds` | `runtime_adapter_flag` | `gate_thresholds` | Corrected. |
| `q_latency_budget` | `mcp_lifecycle` | `latency_budget` | Corrected. |

## Hard Holdout Review

Remaining expected-key failures after `candidate-strong`:

| query | expected | blended rank | blended top | review note |
|---|---|---:|---|---|
| `hh_tool_atlas` | `tool_atlas_snapshot` | 2 | `mcp_dispatch_audit` | Both candidates concern telemetry optimization; side signal does not yet distinguish atlas policy recommendations from raw dispatch audit. |

Winner changes:

| query | baseline top | blended top | verdict |
|---|---|---|---|
| `hh_orphan_inventory` | `memory_orphan_candidates` | `memory_orphan_inventory` | Corrected. |
| `hh_ocr_grounding` | `desktop_snapshot` | `vision_grounding_ocr_readonly` | Corrected. |
| `hh_worktree_create` | `git_topology_preflight` | `worktree_create_parallel` | Corrected. |

## Review Recommendation

Recommended decision:

- Accept `candidate-strong` as an offline-only side-signal policy.
- Do not approve runtime retrieval mutation yet.
- Allow a follow-up runtime-boundary design document only if it preserves:
  read-only fallback, feature gating, no memory writes, no automatic online
  reranking, explicit latency SLOs, and an operator-visible disable switch.

Human reviewer should explicitly approve or reject this recommendation before
the persistent plan marks human review complete.

## Human Decision

Approved: accept `candidate-strong` as an offline-only side-signal policy and
allow a follow-up runtime-boundary design document.

This approval does not enable runtime retrieval mutation. Any implementation
must still preserve read-only fallback, feature gating, no memory writes, no
automatic online reranking, explicit latency SLOs, and an operator-visible
disable switch.
