# Memory Continuity T7 Neural Critic Shadow Eval

Date: 2026-06-19

T7 adds a read-only offline evaluator for neural-critic memory judgments. It
does not run a neural model. It compares externally produced critic labels
against deterministic T3/T4 baseline labels on held-out cases.

## Interface

New MCP tool:

- `memory_neural_critic_shadow_eval`

Inputs:

- `cases`: held-out rows with `expected_label`, `deterministic_label`, and
  `critic_label`.
- `min_cases`: minimum valid held-out rows, default `20`.
- `min_delta_accuracy`: minimum critic accuracy lift over deterministic baseline,
  default `0.01`.
- `max_critic_regressions`: maximum allowed cases where deterministic baseline
  is correct and critic is wrong, default `0`.

Supported labels:

- `stale`
- `duplicate`
- `missing`
- `too_large`
- `ok`

## Decision Model

The report returns schema `agent_bridge.memory_neural_critic_shadow_eval.v0`.

It computes:

- deterministic baseline accuracy
- critic accuracy
- delta accuracy
- critic fixes: deterministic wrong, critic correct
- critic regressions: deterministic correct, critic wrong
- label counts

It returns `ready_for_review=true` only when:

- enough valid held-out cases exist
- critic accuracy beats deterministic accuracy
- delta accuracy meets the threshold
- critic regressions are within the threshold
- labels are valid

Even when ready, the tool still returns:

- `critic_write_authority=false`
- `may_write_memory_now=false`
- `changes_memory_search_order=false`
- `default_search_order_change_allowed=false`
- `runs_neural_model=false`

The next gate is human review before any write or ranking authority.

## Boundary

This tool is read-only. It does not:

- run a neural model
- train, fine-tune, or persist model weights
- call `memory_search`
- write memories, graph edges, feedback labels, or consolidation decisions
- grant write authority, ranking authority, or default retrieval influence
- include raw case IDs, memory keys, queries, or content

The neural critic is only an offline candidate until it beats deterministic
baselines under held-out evaluation and passes a separate review path.

## Verification

Focused tests cover:

- Critic results that do not beat deterministic T3/T4 labels are blocked.
- Critic regressions above threshold are blocked.
- Critic results that beat baseline can become `ready_for_review` but still do
  not gain write authority.
- Raw case IDs, keys, and content supplied in input are not echoed.
- Codex-essential policy exposes `memory_neural_critic_shadow_eval`.

Commands:

```bash
cargo test -p ab-bridge memory_neural_critic_shadow_eval -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture
```

## Next Step

Future work can add a separate producer that runs a real model and emits held-out
critic labels. That producer must remain outside write authority until this
evaluator shows stable lift and a review gate grants the next stage.
