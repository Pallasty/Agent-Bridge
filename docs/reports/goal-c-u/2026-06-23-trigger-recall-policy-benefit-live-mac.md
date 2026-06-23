# Trigger Recall Policy-Benefit Live Mac Eval

Date: 2026-06-23

Scope: extend the `policy_benefit_eval.v0` contract from the portable fixture
to the current live Mac held-out trigger corpus.

This slice does not implement production `enforce_hold`, does not change
default `memory_search`, does not register an MCP tool, does not mutate the
memory DB, does not write graph edges, does not reindex, and does not deploy or
cut over GTE.

## Context

Current master at the start of this slice:

```text
4392bc7 feat(bridge): recall_eval gte-multilingual-base alias detection (runbook Gate 1)
```

Board post #4030 says the GTE Gate 1 code landed, but no live deploy, live
reindex, or cutover has happened. Therefore this report is current Mac e5/384
live-store evidence, not post-GTE evidence.

## Corpus Readiness

Command:

```bash
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
```

Observed:

| Metric | Value |
|---|---:|
| active rows | 3034 |
| trigger rows | 153 |
| projected rows | 153 |
| corpus cases | 30 |
| expected key refs | 30 |
| present expected refs | 30 |
| missing expected refs | 0 |
| expected without trigger | 0 |
| ready | true |

This confirms the current Mac corpus is runnable and non-phantom in the narrow
coverage sense: expected rows exist and still carry trigger projection.

## New Command

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-live-mac
```

It reuses the same machine-readable schema as the fixture:

```text
agent_bridge.memory.trigger_recall.policy_benefit_eval.v0
```

## Live Result

Observed output summary:

| Metric | Value |
|---|---:|
| positive baseline hits | 29/30 |
| positive cases held | 0 |
| true hits lost by shadow gate | 0 |
| accepted order drift | 0 |
| baseline false hits before gate | 18 |
| baseline false hits after gate | 18 |
| false hits removed by shadow gate | 0 |
| held controls by reason | none |

Machine-readable decision:

```text
contract_passed=false
ready_for_production_review=false
production_enforce_hold_authorized=false
next_required_gate=repair_policy_benefit_eval_contract_or_corpus
```

## Interpretation

The live Mac corpus is ready to run, but it does not yet prove policy benefit.

The important failures are:

- one positive case is still not baseline-findable in the live FTS path;
- current negative controls produce 18 baseline false hits;
- the query-intent shadow gate removes none of those false hits;
- no controls are currently classified into held reasons.

Therefore this is not production-review evidence for `enforce_hold`. It is a
diagnostic result that points to either:

- improving the deterministic query-intent classifier so it catches the intended
  contrastive controls without holding legitimate continuations; or
- refining the real held-out policy-benefit corpus so controls actually encode
  the query intents that production would hold.

## Boundary

Do not treat this live Mac run as production approval. It only proves that the
same contract can now be run against the real current Mac corpus and that the
current e5/384 live result is not ready.

After any coordinated GTE reindex/cutover, rerun both:

```bash
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-live-mac
```

and compare the metrics before reopening production `enforce_hold`.
