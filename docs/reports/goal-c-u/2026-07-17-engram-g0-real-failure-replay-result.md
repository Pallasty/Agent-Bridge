# Engram G0 Real-Failure Replay Result

Date: 2026-07-17

Status: **PASS_OBSERVED_RELEVANT_FAILURE / G1 DESIGN ONLY**

## Decision

Two consumer-owned, candidate-preceding Agent-Bridge recall cohorts were replayed against the frozen
`3bf8ad3a67ff02a4e717db8e29e89079f66c01cf` baseline. One current
`overgeneralization_gap` reproduced. This opens only G1 grouped-corpus design.

It does not authorize a real corpus freeze, candidate implementation, retrieval-order mutation, live-store
write, BioCortex experiment, or runtime promotion.

## Provenance

The probes and target labels were already committed in `crates/bridge/examples/recall_eval.rs` before the
engram-inspired direction was selected:

- initial corpus: `2abd93fa94cb63ef5a48febad75520fba968bc93`, 2026-06-19;
- tiered lexical controls: `f43b2c8b99b5ae472e72446b371d07c67af08117`, 2026-06-19;
- consumer-side hard-tier finding: forum thread `#120`, post `#3897`, 2026-06-22;
- case-family reviews: the case #2 tool-surface and case #8 remote-session reports from 2026-06-23.

The baseline source blob SHA-256 was
`03b5a7515f657074b56b119807659e87c7d8bc216c0682e896beeae34d69840a`. The aggregated second-cohort consumer
review receipt was `6a45b042bc978e19dade66ff95d8846ece4c18985e51622296febc99fdfef711`.

## Frozen Baseline

| Field | Value |
|---|---|
| Agent-Bridge binary SHA-256 | `2fcd99a55acb0e433320ada9b058651d46c10500a2ec6459866c3dd504580f30` |
| Environment SHA-256 | `13be7b202d061a1fd37bc2405427ecf1251f85d043b8b5341c8efbc835564f5e` |
| Embedding transport | `loopback_delegated` |
| Perception-filter state | `frozen` |
| Modes | `fts`, `hybrid`, `semantic` |
| Top-k | `10` |

Every probe/mode observation used a fresh clone of one frozen online backup. Both runs reported source
connection `total_changes=[0,0]`, unchanged frozen-base bytes, unchanged durable content/index state, and zero
live memory writes.

## Redacted Results

Ranks are `(fts, hybrid, semantic)` and `0` means the accepted target set was absent from the top 10.

| Episode group | Exact | Related | Unrelated target intrusion | Signature |
|---|---:|---:|---:|---|
| `northstar_vocabulary_bridge_gap` | `(6,5,7)` | `(0,0,10)` | `(0,0,0)` | `no_relevant_gap` |
| `tool_surface_taxonomy_gap` | `(2,8,5)` | `(0,0,4)` | `(0,0,0)` | `no_relevant_gap` |
| `remote_session_steering_gap` | `(1,7,1)` | `(0,0,1)` | `(0,0,3)` | `overgeneralization_gap` |

The first two historical hard misses are now recovered by the current semantic baseline. They cannot be used
to claim a remaining generalization failure. The remote-session target, however, also appears at semantic rank
3 for its independently frozen unrelated control. Exact and related probes both pass, so this is not an
ordinary retrieval miss; it is a current specificity failure.

The admitted packet receipt is:

```text
packet_id = hard_miss_cohort_20260622_23_g0
packet_sha256 = feb5c8c639f48a6179144cfbe6b16a548aef91a127840c37640b7673a88c97e1
g0_verdict = PASS_OBSERVED_RELEVANT_FAILURE
relevant_group_count = 1
ready_for_g1_grouped_corpus_design = true
```

The earlier Northstar-only no-gap packet SHA-256 was
`545c9f0656f8cbbaa080acc3250fd12d644d163cd6094c0d0b1ac5cb5fa94517`.

## Interpretation

The observed application need is currently **specificity control**, not additional related-context lift. Any
later experiment must therefore make unrelated-target intrusion the primary metric and treat exact and related
retrieval as non-inferiority constraints. A mechanism that merely broadens recall would move in the wrong
direction for the admitted failure.

This result is one FIT-only incident, not a corpus or a sample-size claim. G1 must independently define episode
custody, FIT/development/sealed partitions, baseline roster, metrics, budgets, and reviewer separation before
any candidate code can be considered.
