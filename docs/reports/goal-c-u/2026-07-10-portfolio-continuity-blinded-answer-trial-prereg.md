# Portfolio Continuity Blinded Answer Trial Preregistration

Date: 2026-07-10

Status: **PRE-REGISTERED**; no real/private context capture or trial answer was
run before this contract was committed.

Forum thread: `design#119`, start post `3037`

AB anchors:

- Scope memory: `portfolio_continuity_blinded_answer_trial_scope_20260710`
- Evidence-surface result:
  `portfolio_continuity_ab_native_surface_trial_completed_20260710`
- S4 implementation: `s4_compact_projection_impl_20260710`

## Purpose

The preceding AB-native trial measured whether each memory surface carried the
required evidence. It did not test whether one fixed model could turn that
context into a complete, current, useful answer without unsupported claims.

This gate performs that answer-stage comparison while keeping the reviewer
blind to condition identity. It can recommend a larger answer trial only. It
cannot promote any runtime behavior.

```yaml
schema: agent_bridge.portfolio_continuity_answer_contract.v0
contract_id: portfolio_continuity_answer_blind_20260710
prereg_base_commit: 97c3b7dbf39ccb565b03656e4be83d507b5feb10
runtime_source_commit: a8c6302325e27c9b5cb20f8c958ab719666de372
contract_sha256: f1dbaa335f082d329c2fe01d3681df14046df720351d22d300663bcb4a6acd1f
blind_seed_sha256: bc08a39664fb3151f046538560f0922fa592ca36975d3f9e6f23f313f6144428
recommendation_scope: expanded_trial_only
runtime_promotion_allowed: false
```

## Fixed Conditions

The same two already-hashed strategic prompt classes are used in every
condition. Search mode is hybrid, limit is 10, and `skill` rows are excluded.

| Condition | Context construction |
| --- | --- |
| `hybrid_retrieval` | Full records from `memory_search(compact=false)` |
| `compact_then_get_top2` | Compact search page plus `memory_get` for the first two unique ranked keys |
| `session_bootstrap` | Current session bootstrap for the exact question |
| `portfolio_digest` | Direct read of the existing portfolio digest |

Top-2 selection is rank-only. It cannot use claim labels, human relevance
judgment, answer quality, or memory-key special cases. Full and compact search
must return the same ranked key sequence or capture fails.

## Isolation

The collector opens production SQLite read-only and makes one consistent online
backup. Every case/condition receives a separate copy of that backup and a
separate MCP process. Retrieval telemetry, coactivation, and access-count side
effects therefore cannot cross conditions or reach the live store.

Each process must log its exact temporary database path. Every copy starts with
the same SHA-256, and all copies are removed after collection. Raw prompts,
contexts, result records, and keys remain in ignored `data/`.

## Fixed Generator

```yaml
cli: codex-cli 0.144.1
model: gpt-5.4
reasoning_effort: medium
independent_invocations: true
workspace: empty_ephemeral_read_only
user_config_loaded: false
project_rules_loaded: false
tool_use_allowed: false
external_facts_allowed: false
max_answer_chars: 6000
```

Every answer is generated in a new process with the same instruction. Evidence
is explicitly untrusted data rather than executable instruction. The model must
answer in the question's language, use only explicit evidence, state
insufficiency rather than infer, and avoid condition names, retrieval methods,
memory keys, or evaluation narration. A tool-call event invalidates the run.

The configured Codex provider necessarily receives the private question and
condition context for generation. No other model receives them, and no LLM is
used as a judge.

## Blinding

The private 32-byte seed is committed only by the SHA-256 above. It determines
generation order, opaque answer ids, and answer order. The owner packet contains
the question, rubric, opaque ids, and answers, but no context, condition label,
or mapping. The mapping is stored in a separate ignored file.

The scorer refuses to unblind unless:

1. contract, capture, generation, blind packet, map, and review hashes match;
2. every answer is reviewed exactly once;
3. every required claim has a `0/1/2` completeness score;
4. currentness, unsupported-assertion count, and usefulness are populated;
5. each case has one opaque preference or an explicit tie.

Until then, status is `WAIT_OWNER_BLIND_REVIEW`.

## Review Metrics

- Required-claim completeness: `0` absent, `1` partial, `2` complete, weighted
  by the preregistered claim weights.
- Currentness: `pass`, `uncertain`, or `fail`.
- Unsupported assertions: non-negative count.
- Usefulness: integer `1..5`.
- Per-case preference: one opaque answer id or `tie`, entered after independent
  scoring.

## Advance Threshold

The full-hybrid reference must itself pass the absolute gate. A candidate can
advance only when all of these are true:

- weighted completeness is at least `0.90`;
- currentness failures and uncertainties are both zero;
- unsupported assertions are zero;
- mean usefulness is at least `4.0`, with no case below `3`;
- completeness does not drop versus full hybrid;
- usefulness drops by no more than `0.5` versus full hybrid;
- currentness and unsupported assertions are no worse than full hybrid;
- context tokens are at least `40%` lower than full hybrid.

Only `compact_then_get_top2` and `portfolio_digest` are candidate conditions.
Session bootstrap remains a diagnostic comparator.

## Boundaries

- No raw prompt, context, answer, mapping, seed, or review is checked into git.
- No live Agent-Bridge store write is allowed.
- No LLM judge or automatic unblinding is allowed.
- No result from two prompts is a benchmark or generalization claim.
- Readiness means expanded-trial evidence only.
- Automatic digest regeneration remains forbidden.
- Compact search remains opt-in; no default-path change is authorized.
- No retrieval/runtime, version, tag, release, or CI action is authorized.

## Repository Files

```text
scripts/eval/portfolio_continuity_answer_trial.py
scripts/eval/fixtures/portfolio_continuity_answer_contract.json
scripts/verify-portfolio-continuity-answer-trial.sh
docs/reports/goal-c-u/2026-07-10-portfolio-continuity-blinded-answer-trial-prereg.md
```

## Pre-Commit Verification

The synthetic verifier exercises the full capture, generation, blinding,
review, and score chain with fake Agent-Bridge and Codex executables. One
additional one-call Codex CLI compatibility smoke used a synthetic question and
synthetic context to confirm the preregistered CLI flags and JSONL event parser.
It used no real prompt, AB memory content, condition mapping, or trial answer.

## Execution Order

1. Commit and push this preregistration contract and synthetic verifier.
2. Build the private spec with that exact commit and the committed seed.
3. Capture all eight case/condition contexts from isolated snapshot copies.
4. Generate eight independent fixed-model answers.
5. Give only the blind packet and review template to the owner.
6. Stop at `WAIT_OWNER_BLIND_REVIEW` until the completed review is returned.
7. Unblind and score only through the hash-bound scorer.
