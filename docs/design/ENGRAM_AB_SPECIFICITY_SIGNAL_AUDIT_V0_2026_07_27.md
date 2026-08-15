# Engram AB Specificity Signal Audit v0

Date: 2026-07-27

Status: **COMPLETED — NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL**

## Objective

This gate reconnects the engram-reorganization hypothesis to the observed
Agent-Bridge `remote_session_steering_gap`. It asks whether the target already
has enough trustworthy local graph structure to justify implementing an
offline `clustered_reorganization` scout.

The observed application problem is specificity: exact and related retrieval
were retained while an unrelated probe retrieved the same target. Broadening
the candidate set is therefore not a valid default response.

## Input and output boundary

`scripts/eval/engram_ab_specificity_signal_audit.py` requires an explicitly
supplied SQLite snapshot. It opens that file with SQLite `mode=ro` and
`immutable=1`, enables `query_only`, runs `quick_check(1)`, and verifies that
the file SHA-256 is unchanged after the audit.

The tool reads only:

- target status and scope;
- aggregate target edge counts by type;
- aggregate scope membership for target `evolved` edges;
- aggregate target coactivation count, maximum repeat count, and consolidated
  count.

It does not read or emit memory content, raw queries, embeddings, retrieved
rows, reviewer packets, or private G0/G1 material.

## Admission rule

The scout may proceed only when at least one pre-existing trusted signal family
is present:

- two or more crystallized `cofires`/`co_referenced` edges; or
- two or more consolidated coactivation neighbors.

`evolved` edges are reported diagnostically but never count as trusted cluster
support. Raw coactivation rows with no consolidation likewise do not qualify.

The two possible results are:

- `READY_FOR_OFFLINE_CLUSTER_SCOUT`;
- `NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL`.

Neither result authorizes candidate implementation, retrieval mutation,
memory/graph writes, integration, deployment, or live acceptance.

## Observed result

The frozen 2026-07-27 snapshot had no trusted `cofires` or `co_referenced`
neighbor, 19 one-shot coactivation neighbors with no consolidated neighbor, and
31 `evolved` neighbors of which only three belonged to Agent-Bridge. The graph
gate therefore returned:

```text
NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL
```

No graph-cluster candidate was implemented. A separately authorized,
non-graph diagnostic and conditional runtime candidate are recorded in
`docs/reports/goal-c-u/2026-07-27-engram-ab-specificity-scout-result.md`.

## Reproduction

```bash
python3 scripts/eval/engram_ab_specificity_signal_audit.py \
  --db /path/to/frozen/state.db \
  --target-key agentbridge_remote_session_steer_gap_20260529 \
  --project-suffix agent-bridge \
  --pretty
```

Run unit coverage with:

```bash
python3 -m unittest tests/test_engram_ab_specificity_signal_audit.py
```
