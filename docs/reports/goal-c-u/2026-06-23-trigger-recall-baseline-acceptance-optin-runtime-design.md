# Trigger Recall Baseline Acceptance Opt-In Runtime Design - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Worktree: `/Data/CascadeProjects/agent-bridge`

Base: `7e6e731` (`test(memory): add trigger baseline acceptance audit`)

Scope: design-only; no runtime implementation

## Purpose

The baseline acceptance audit showed a clean eval-only result on the current
Aio2 trigger corpus:

| Metric | Value |
|---|---:|
| positive cases held | 0 |
| true hits lost by shadow gate | 0 |
| baseline false hits before shadow gate | 23 |
| baseline false hits after shadow gate | 0 |

That is strong evidence that a query-intent baseline hold is worth designing.
It is not yet authority to change default `memory_search`.

This report defines the next runtime shape: an explicit opt-in mode for trigger
baseline acceptance, including the user-visible fallback semantics for held
baseline queries.

## Current Runtime Anchor

The production MCP `memory_search` tool currently returns a bare JSON array of
hits. Its shape is intentionally simple:

1. parse `query`, `tags_any`, `limit`, `mode`, `scope`, `scope_mode`,
   `include_global`, `expand_top`, `rrf_k`, `threshold`, and `exclude_kinds`;
2. call the selected store search path;
3. apply scope handling, Seed boost, coactivation rerank, output filters, and
   truncation;
4. emit only the visible hit list.

That response shape cannot safely express:

```text
the query was intentionally held by an opt-in policy, and this is not the same
thing as an ordinary empty search
```

Therefore the first baseline acceptance runtime candidate should not be a
silent filter inside the default `memory_search` hit array.

The closest existing pattern is `memory_search_biocortex_opt_in`: a protected
wrapper that leaves default `memory_search` unchanged, returns a response
contract, and redacts raw query/key/content from its audit.

## Decision

Use a separate protected opt-in wrapper first.

Recommended names for a future implementation:

| Layer | Suggested Name | Purpose |
|---|---|---|
| pure policy module | `trigger_query_intent` | deterministic allow/hold reason labels |
| store wrapper | `memory_search_trigger_acceptance_opt_in` | baseline search plus response contract |
| MCP surface | `memory_search_trigger_acceptance_audit` | explicit diagnostic/opt-in tool |

Do not add enforcement to default `memory_search` in the first production
candidate.

If a later MCP design chooses to add fields to `memory_search`, they must be
strictly default-off and must return a richer object when enabled. They must
not overload the existing bare array response with policy semantics.

## Runtime Options

Suggested option struct for a future store wrapper:

```text
TriggerBaselineAcceptanceOptInOptions {
  mode: off | audit_only | enforce_hold,
  per_call_opt_in: bool,
  runtime_enabled: bool,
  operator_approved: bool,
  operator_disabled: bool,
  scope_mode: local_only,
  regression_anchor: aio2_trigger_recall_baseline_acceptance_shadow_20260623,
  include_audit: bool
}
```

Mode semantics:

| Mode | Returned Hits | Audit |
|---|---|---|
| `off` | current baseline hits | optional `blocked_to_baseline` |
| `audit_only` | current baseline hits | `would_hold` or `allow` |
| `enforce_hold` | hits only when query intent allows | `held` or `allow` |

The default must be `off`.

## Authorization Gates

All of these gates must pass before `enforce_hold` can affect visible results:

| Gate | Required State |
|---|---|
| per-call opt-in | true |
| runtime enabled | true |
| operator approved | true |
| operator disabled | false |
| retrieval mode | `fts` |
| scope mode | `local_only` |
| baseline search | completed or deliberately skipped by pre-gate design |
| regression anchor | latest baseline acceptance audit passed |
| response shape | can express `held` distinctly from empty results |

If any authorization gate is missing, the wrapper must fail open to baseline
results and report the blocker in audit. It must not partially enforce a hold.

## Fallback Semantics

Held baseline queries need an explicit user-visible state.

Recommended response contract:

```json
{
  "schema": "agent_bridge.memory.trigger_baseline_acceptance_opt_in.v0",
  "mode": "enforce_hold",
  "status": "held",
  "hits": [],
  "baseline_hit_count": 10,
  "returned_hit_count": 0,
  "default_memory_search_unchanged": true,
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "fallback_behavior": "diagnostic_hold_not_empty_search",
  "audit": {
    "query_hash": "sha256:...",
    "raw_query_included": false,
    "raw_keys_included": false,
    "content_included": false,
    "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623"
  }
}
```

The important distinction:

- ordinary empty search means no hits were found;
- held search means hits may exist, but this opt-in policy withheld them;
- blocked/malformed opt-in means the wrapper returned baseline hits instead of
  enforcing.

Suggested status values:

| Status | Meaning |
|---|---|
| `returned_baseline` | wrapper is off, blocked, or audit-only fallback returned baseline |
| `returned_accepted` | opt-in mode allowed the query and returned baseline hits |
| `would_hold` | audit-only mode detected a hold but returned baseline hits |
| `held` | enforce mode withheld baseline hits with an explicit reason |

## Side-Effect Boundary

The future implementation must not be built as:

```text
call the existing MCP MemorySearchTool, then post-filter its JSON response
```

That would be too late in the pipeline and could mix hold decisions with output
formatting, telemetry, and coactivation behavior.

Preferred implementation boundary:

1. run query-intent policy before any enforced hold response;
2. call the store baseline search only when the chosen mode needs baseline
   counts or allowed hits;
3. record MCP coactivation traces only for hits actually returned to the user;
4. never record coactivation traces for withheld hits;
5. keep access-count and query telemetry semantics explicit in the response
   contract.

The eval harness remains read-only and side-effect-free. A production wrapper
must document any intentional telemetry/access side effect before merge.

## Query-Intent Labels

The first runtime candidate should reuse the eval labels exactly:

| Reason | Meaning |
|---|---|
| `write_bypass_intent` | asks to directly write, bypass review, or bypass dry-run gates |
| `creative_non_continuation_intent` | asks for creative writing while sharing project vocabulary |
| `frontend_dashboard_intent` | dashboard/state wording is frontend or visual-design intent |
| `health_dashboard_intent` | Controlled RSI/dashboard wording is health/workout intent |

Accepted continuation queries should preserve baseline hits and order.

## Audit Requirements

The opt-in audit must be redacted by default:

| Field | Requirement |
|---|---|
| raw query | not included by default |
| raw keys | not included by default |
| memory content | never included in compact audit |
| query hash | required |
| baseline count | allowed |
| returned count | allowed |
| reason label | required for holds |
| regression anchor | required |
| default search unchanged flag | required |

Suggested schema:

```text
agent_bridge.memory.trigger_baseline_acceptance_opt_in.v0
```

The audit must clearly state whether it changed visible results:

| Field | Meaning |
|---|---|
| `changes_default_memory_search` | always false |
| `changes_this_opt_in_call` | true only for `enforce_hold` with `held` |
| `baseline_returned` | true when baseline hits are visible |
| `withheld_baseline_hits` | true only for explicit `held` responses |

## Regression Gate

No implementation should move beyond `audit_only` unless these commands pass:

```bash
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-runtime-audit
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
cargo check -p ab-bridge --examples
```

Required eval results:

| Requirement | Value |
|---|---:|
| Aio2 corpus ready | true |
| positive cases held | 0 |
| true hits lost by baseline shadow gate | 0 |
| baseline false hits after shadow gate | 0 |
| runtime-shaped supplemental false hits after gate | 0 |
| trigger recall tests | all pass |

If any positive case becomes held, implementation must stop at `audit_only`
until the reason is reviewed.

## Implementation Ladder

Recommended next slices:

1. extract deterministic trigger query-intent helpers from the eval example
   into a small pure module, with tests copied from the eval control set;
2. add a store-level opt-in response contract in `audit_only` only;
3. add a diagnostic MCP surface that returns the richer response object;
4. run the Aio2 regression gate and post the report;
5. only after review, add `enforce_hold` behind all authorization gates;
6. keep default `memory_search` unchanged until a separate production
   authorization explicitly changes it.

## Non-Goals

This design does not authorize:

- changing default `memory_search`;
- returning empty arrays for held queries without a `held` status;
- changing ranking or candidate order for accepted baseline hits;
- changing tokenizer/schema/indexing;
- memory reindexing;
- semantic or graph expansion;
- graph/PageRank/coactivation as acceptance evidence;
- memory writes or GHP materialization;
- hidden enforcement in `hybrid` or `semantic` modes.

## Open Questions

- Whether the first MCP surface should be named as an audit tool or an opt-in
  search tool.
- Whether `audit_only` should include `hits` by default, or return counts plus a
  separate `include_hits` flag.
- Whether `enforce_hold` should run query-intent before baseline search to avoid
  any baseline-side telemetry, or after baseline search to report accurate
  baseline hit counts.
- Whether the query-intent helper belongs in `ab-store`, `ab-bridge`, or a
  smaller shared crate.
