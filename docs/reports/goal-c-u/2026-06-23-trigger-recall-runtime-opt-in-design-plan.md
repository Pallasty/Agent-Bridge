# Trigger Recall Runtime Opt-In Design Plan - 2026-06-23

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Report timestamp: `2026-06-23T11:07:56Z`

Worktree: `/Data/CascadeProjects/agent-bridge`

Base: `12edee8` (`docs(memory): sync u report with trigger audit`)

Scope: verification plus production-facing design plan; no runtime implementation

## Verdict

The current evidence is strong enough to design the next opt-in runtime control
plane, but not to touch default `memory_search`.

Recommended next shape:

- add a separate trigger-recall opt-in control surface, modeled after the
  BioCortex gated-store-trial pattern;
- keep `memory_search` schema and default behavior unchanged;
- make baseline acceptance an explicit `fts`-only, per-call opt-in trial;
- for rejected baseline queries, return a `hold` packet with audit fields, not
  an ordinary empty production search result.

## Status Rechecked

Repository:

| Check | Value |
|---|---|
| local branch | `master` |
| remote sync | fast-forwarded to `origin/master` |
| HEAD | `12edee8` |
| worktree before design edit | clean |

Board:

- Thread #105 had no posts after #2500 when checked from this session.
- The latest Goal C U standing report landed in `12edee8` and names this exact
  lane as the next useful aio2 action.

Latest standing U read:

- held-out hard-tier recall remains the primary production anchor;
- trigger recall evidence is explicitly aio2-native and eval-only;
- next aio2 action is a production-facing opt-in design review, not another
  trigger eval family;
- graph/PageRank/centrality remains diagnostic only.

## Evidence Replayed

Preflight:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
```

Result:

| Metric | Value |
|---|---:|
| active rows | 454 |
| trigger rows | 26 |
| projected rows | 25 |
| corpus cases | 14 |
| expected refs present | 14 |
| missing expected refs | 0 |
| expected without trigger | 0 |
| ready | true |

Aio2 eval:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
```

Key result:

| Mode | R@1 | R@5 | R@10 | MRR | False Hits |
|---|---:|---:|---:|---:|---:|
| `baseline_fts` / `intent_projected` | 0.714 | 0.857 | 0.857 | 0.786 | 23 |
| `projected_union` | 0.714 | 1.000 | 1.000 | 0.857 | 23 |
| `union+policy` | 0.714 | 1.000 | 1.000 | 0.857 | 5 |
| `union+cont` | 0.714 | 1.000 | 1.000 | 0.857 | 0 |

Runtime-shaped supplemental audit:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-runtime-audit
```

Result:

| Metric | Value |
|---|---:|
| supplemental recovered baseline misses | 2 (`#3`, `#9`) |
| runtime final lost baseline hits | 0 |
| supplemental false hits after gate | 0 |
| baseline false hits retained | 23 |
| runtime final false hits | 23 |

Baseline acceptance shadow audit:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result:

| Metric | Value |
|---|---:|
| baseline-shadow R@10 | 0.857 |
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits before shadow gate | 23 |
| baseline false hits after shadow gate | 0 |
| false hits removed by shadow gate | 23 |

Held controls by reason:

| Reason | Controls |
|---|---:|
| `creative_non_continuation_intent` | 2 |
| `frontend_dashboard_intent` | 2 |
| `health_dashboard_intent` | 1 |
| `write_bypass_intent` | 2 |

## Runtime Shape Decision

Do not add a hidden or defaulted parameter to `memory_search` in the first
runtime slice.

Reason:

- `memory_search` currently has a broad public contract: `query`, `tags_any`,
  `scope`, `scope_mode`, `include_global`, `limit`, `mode`, hybrid knobs,
  semantic threshold, and `exclude_kinds`.
- Its execution path immediately calls one of `store.memory_search`,
  `store.memory_search_hybrid`, or `store.memory_search_semantic`, then applies
  scope filtering, Seed boost, coactivation rerank/write, output filtering,
  telemetry, and JSON result return.
- Adding baseline acceptance inside that path would couple query-intent holds
  to existing coactivation, telemetry, and result-array semantics too early.

The safer pattern already exists in BioCortex:

- read-only status/dry-run/review/transition gates first;
- explicit `per_call_opt_in`;
- mode restricted to `fts`;
- operator disable switch;
- gated store trial as a separate surface;
- redacted hashes/counts by default;
- tests proving blocked gates do not call `memory_search` and do not leak raw
  query/key/content.

Trigger recall should copy that pattern.

## Proposed Control Plane

### Slice 1: Read-Only Status And Transition Gate

Add design-compatible surfaces first:

| Surface | Calls Store Search? | Purpose |
|---|---:|---|
| `trigger_recall_opt_in_status` | no | report runtime env, per-call opt-in, mode, scope, and audit-shape readiness |
| `trigger_recall_opt_in_runtime_transition_gate` | no | consume readiness/eval metrics and decide whether a requested transition may proceed |

Required runtime gates:

| Gate | Required |
|---|---|
| `mode` | `fts` only |
| `per_call_opt_in` | true |
| scope | exact project/local scope required |
| operator enable | `AB_TRIGGER_RECALL_OPT_IN=1` |
| operator disable | `AB_TRIGGER_RECALL_DISABLE=1` blocks |
| regression anchor | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| default search | unchanged |

The transition gate should block if any of these are true:

- missing per-call opt-in;
- non-`fts` mode;
- no exact local project scope;
- operator disabled;
- eval metrics are stale or absent;
- `union+cont` has misses or false hits;
- baseline shadow loses any true positive;
- baseline shadow holds any positive case;
- baseline shadow leaves any current negative-control false hit;
- requested payload includes raw query/content/keys outside the explicit trial
  input boundary.

### Slice 2: Gated Baseline Acceptance Trial

Add a separate trial surface, not a `memory_search` parameter:

```text
trigger_recall_opt_in_gated_baseline_trial
```

Inputs:

- `runtime_transition_gate`;
- `query`;
- `tags_any`;
- `limit`;
- `mode=fts`;
- `scope`;
- `scope_mode=local_only`;
- `per_call_opt_in=true`;
- optional `attempt_id` and `commit`.

Behavior:

1. If the transition gate blocks, do not call `memory_search`.
2. If the transition gate allows, call baseline `memory_search` with the same
   `fts` contract the user would otherwise get.
3. Run the deterministic query-intent decision.
4. Emit a redacted audit object.
5. If accepted, return a trial result with normal baseline hits plus audit.
6. If rejected, return a `hold` packet with `visible_hits=[]`, baseline hit
   count/order hash, and reject reason.

Important: a rejected baseline query is not an ordinary empty search. The
status is `held_by_query_intent`, not `search_completed_no_results`.

### Slice 3: Optional Supplemental Trial

Do not combine this with baseline acceptance in the same first implementation.

The supplemental path needs a store-backed projected/trigger candidate source.
That source is not yet part of `memory_search`; the eval harness uses in-memory
scratch FTS over `fts_content`.

A later supplemental trial should choose one source explicitly:

| Source | Status |
|---|---|
| scratch FTS in example harness | proven eval-only |
| store-backed `fts_content` projected query | candidate implementation |
| persistent trigger projection side table | future design |

Until that source is chosen, the first runtime-facing trial should focus on
baseline acceptance semantics.

## Audit Contract

Recommended schema:

```text
agent_bridge.memory.trigger_recall.opt_in_baseline_trial.v0
```

Required fields:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.opt_in_baseline_trial.v0",
  "read_only": true,
  "mode": "fts",
  "per_call_opt_in": true,
  "default_memory_search_unchanged": true,
  "calls_memory_search": true,
  "writes_memory": false,
  "writes_graph_edges": false,
  "records_coactivation": false,
  "query_hash": "sha256:...",
  "scope_mode": "local_only",
  "baseline_candidates_before_gate": 10,
  "baseline_candidates_after_gate": 0,
  "baseline_order_hash_before_gate": "sha256:...",
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "visible_behavior": "held_by_query_intent",
  "fallback_behavior": "hold_packet_not_empty_search",
  "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623",
  "changes_default_memory_search_order": false,
  "changes_default_memory_search_schema": false,
  "changes_production_retrieval_default": false
}
```

For an accepted query:

- `visible_behavior`: `baseline_fts_visible`;
- `baseline_candidates_after_gate`: same as before gate;
- reject reason: `null`.

For a blocked transition:

- `status`: `transition_gate_blocked`;
- `calls_memory_search`: false;
- raw query/key/content not echoed.

## User-Visible Semantics

The first runtime-facing baseline acceptance trial must not use an ordinary
empty result array for rejected queries.

Allowed:

- `status=held_by_query_intent`;
- `visible_hits=[]`;
- `baseline_candidate_count_before_gate=N`;
- redacted baseline order hash;
- deterministic reject reason;
- link to regression anchor.

Forbidden in the first runtime-facing slice:

- returning `[]` as if `memory_search` naturally found nothing;
- changing default `memory_search`;
- hiding the reject reason;
- running in `hybrid` or `semantic`;
- using graph/semantic/coactivation as acceptance evidence;
- writing memory or graph rows;
- adding coactivation traces for held candidates.

## Implementation Plan

1. Land this design packet.
2. Add read-only `trigger_recall_opt_in_status` and
   `trigger_recall_opt_in_runtime_transition_gate` surfaces with tests.
3. Add `trigger_recall_opt_in_gated_baseline_trial` as a separate, non-default
   tool. Tests must prove blocked gates do not call `memory_search` and do not
   leak raw query/key/content.
4. Run a redacted batch diagnostic over the 14 positive cases and 8 negative
   controls through the gated trial.
5. Write a production review packet comparing:
   - default `memory_search`;
   - gated baseline trial allowed queries;
   - gated baseline trial held queries;
   - eval-only supplemental `union+cont`.
6. Only after that review, decide whether an MCP-visible opt-in retrieval mode
   should return user-visible hits or remain diagnostic-only.
7. Keep default `memory_search` unchanged until a separate authorization
   explicitly approves default behavior change.

## Falsifiers

Stop before implementation if any of these happen:

- latest thread #105 or controlling Mac thread changes the boundary;
- `--check-aio2-native` is no longer ready;
- `union+cont` has any miss or false hit on current controls;
- baseline shadow loses a true hit or holds a positive case;
- baseline shadow leaves any current false hit;
- default `memory_search` hard-tier held-out anchor is represented as improved
  by trigger-only evidence;
- the design requires graph/PageRank/semantic/coactivation signals;
- the first implementation would add a default `memory_search` parameter or
  alter result-array semantics.

## Current Recommendation

Proceed with Slice 1 next: read-only status plus transition gate.

Do not implement the gated baseline trial in the same commit. Keeping the gate
separate gives us a clean review point and mirrors the safest existing
BioCortex control-plane pattern.

This report does not add an MCP tool, mutate runtime state, change retrieval
order, write memory, reindex, change schema, deploy, or authorize an executor.
