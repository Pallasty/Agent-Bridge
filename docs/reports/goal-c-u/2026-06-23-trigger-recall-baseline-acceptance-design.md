# Trigger Recall Baseline Acceptance Design - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Worktree: `/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge`

Base: `769f514` (`test(memory): add case8 remote-session eval assembler`)

Scope: design-only; no runtime implementation

## Why

The previous runtime-shaped trigger audit proved a useful but narrow thing:

```text
baseline FTS + gated supplemental projected candidates
```

Result from
`docs/reports/goal-c-u/2026-06-23-trigger-recall-runtime-shaped-audit.md`:

| Metric | Value |
|---|---:|
| supplemental recovered baseline misses | 2 (`#3`, `#9`) |
| runtime final lost baseline hits | 0 |
| supplemental false hits after gate | 0 |
| baseline false hits retained | 23 |
| runtime final false hits | 23 |

That means supplemental gating is safe for recall expansion, but it does not
solve false hits already produced by baseline FTS. This design separates the
next question: can baseline FTS candidates be shadow-accepted or shadow-held by
query intent without damaging legitimate continuation recall?

## Current Boundary

No production baseline filter exists or is authorized.

Current safe facts:

- `union+cont` can make the projected-union eval path clean by rejecting whole
  query intents before candidate acceptance;
- runtime-shaped supplemental gating can recover misses without adding
  supplemental false hits;
- preserving baseline FTS also preserves baseline false hits;
- therefore any baseline filter must be evaluated as a separate shadow policy,
  not smuggled into the supplemental gate.

## Proposed Eval Shape

Add a future eval-only mode, for example:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

It should model three rows:

| Mode | Meaning |
|---|---|
| `baseline_fts` | current projected FTS behavior, no query-intent filtering |
| `baseline_shadow_accept` | baseline FTS candidates are visible only when query intent is accepted |
| `baseline_shadow_hold` | rejected query intent produces a hold/diagnostic decision, not a user-visible empty production search |

The output must distinguish:

- candidate retrieval;
- query-intent decision;
- would-be visible candidates;
- false hits removed;
- true hits lost;
- reason labels.

## Acceptance Policy

The first baseline shadow gate should be query-level, not candidate-level.

Allowed query intents:

- normal continuation queries;
- legitimate project-state review queries with risky words but no bypass intent;
- dry-run/materialization review queries that explicitly ask to inspect
  evidence rather than perform writes;
- Goal C dashboard/state continuation queries that carry continuity,
  report-first, U-report, executor/no-executor, or governed self-improvement
  context.

Rejected query intents:

| Reason | Meaning |
|---|---|
| `write_bypass_intent` | asks to directly write, bypass review, or bypass dry-run gates |
| `creative_non_continuation_intent` | asks for poetry/creative writing while sharing project vocabulary |
| `frontend_dashboard_intent` | dashboard/state wording is frontend/visual-design intent, not project continuation |
| `health_dashboard_intent` | Controlled RSI/dashboard wording is health/workout intent, not recursive self-improvement |

Important distinction:

- For supplemental candidates, rejection means "drop supplemental candidates
  and use baseline FTS".
- For baseline candidates, rejection must be reported as a shadow hold in eval.
  It must not become production behavior without a separate approval gate.

## Audit Contract

The baseline acceptance audit should be redacted by default. It may include
case/control ids in eval output, but the JSON object should not echo raw query
or raw memory content.

Suggested JSON:

```json
{
  "schema": "agent_bridge.memory.trigger_baseline_acceptance_shadow.v0",
  "read_only": true,
  "mode": "fts",
  "default_memory_search_unchanged": true,
  "query_hash": "sha256:...",
  "baseline_candidates_before_gate": 10,
  "baseline_candidates_after_shadow_gate": 0,
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "visible_behavior_if_production": "not_authorized_shadow_only",
  "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623"
}
```

## Required Regression Checks

Before any production design, the eval-only baseline shadow mode must report:

Recall preservation:

- no true hits lost on the 14-case AIO2-native corpus for accepted queries;
- explicit listing of any rejected positive case, with reason;
- #3 and #9 remain handled by the supplemental runtime-shaped path, not by
  pretending baseline FTS recovered them.

False-hit reduction:

- baseline false hits before shadow gate;
- baseline false hits after shadow gate;
- false hits removed by reason bucket;
- false hits that remain because their query intent is allowed or unknown.

Acceptance controls:

| Control | Expected |
|---|---|
| English write-bypass | reject `write_bypass_intent` |
| Chinese write-bypass | reject `write_bypass_intent` |
| English poetry | reject `creative_non_continuation_intent` |
| Chinese poetry | reject `creative_non_continuation_intent` |
| G25 store-write continuation | allow |
| G26 write-evidence continuation | allow |
| GHP-1b dry-run review | allow |
| GHP-1b tiny write packet review | allow |
| Chinese materialization review without bypass | allow |
| Goal C dashboard/state boundary | allow |
| Goal C dashboard/state closure | allow |
| frontend dashboard/state | reject `frontend_dashboard_intent` |
| Controlled RSI health dashboard | reject `health_dashboard_intent` |

## Non-Goals

This design does not authorize:

- production `memory_search` filtering;
- returning empty production results for rejected baseline queries;
- changing ranking or candidate order;
- changing tokenizer/schema/indexing;
- memory reindexing;
- semantic expansion;
- graph/PageRank/coactivation influence;
- memory writes;
- GHP materialization.

## Implementation Boundary

If accepted, the next code slice should:

1. add the eval-only `--aio2-baseline-acceptance-audit` mode;
2. reuse existing policy and continuation-intent reason labels;
3. print before/after false-hit counts and true-hit loss counts;
4. add unit tests proving allowed continuation queries keep baseline hits and
   rejected controls become shadow holds;
5. keep the existing `--aio2-runtime-audit` behavior unchanged.

The production ladder after that remains separate:

1. eval-only baseline shadow evidence;
2. review report;
3. pinned/snapshot replay if the result looks promising;
4. explicit production design review;
5. only then discuss a runtime flag or MCP-visible opt-in.

## Worktree Note

At the time of this design slice, `crates/bridge/examples/recall_eval.rs` had
an unrelated unstaged local modification from the main-recall/remote-session
line. This design does not edit, stage, or depend on that file.
