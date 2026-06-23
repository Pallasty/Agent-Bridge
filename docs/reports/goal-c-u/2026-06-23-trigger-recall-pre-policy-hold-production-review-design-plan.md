# Trigger Recall Pre-Policy Hold Production Review Design Plan

Date: 2026-06-23

Scope: docs-only design plan for the next production-review packet around
`trigger_recall_opt_in_pre_policy_hold_simulation` and the future
`enforce_hold` lane.

This plan does not implement production `enforce_hold`, does not approve a
production rollout, does not change default `memory_search`, does not expose any
non-Niche tool, and does not write memory, graph edges, indexes, or
coactivation state.

## Pre-Planning Verification

Verified before writing this plan:

```text
HEAD = origin/master = 7cd8292 test(memory): add pre-policy hold runtime smoke script
worktree = clean before this docs-only plan
forum thread 105 latest relevant post = #2522
```

Repeatable installed-binary smoke:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
```

Result: passed against `/home/pallasting/.local/bin/agent-bridge.real`.

Key observations:

- all-profile tool count: `273`;
- `trigger_recall_opt_in_pre_policy_hold_simulation` present;
- approved held path: `held_by_query_intent`, `store_search_called=false`;
- approved accepted path: `returned_accepted`, `store_search_called=true`;
- missing approval path: `blocked_to_baseline`;
- operator disabled path: `operator_disabled`;
- `all_memory_search_mcp_called_false=true`;
- `all_read_only=true`;
- `raw_payload_leak_check=true`;
- production `enforce_hold` remains unauthorized.

Portable Stage-2 fixture:

```text
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
```

Result: passed with existing warnings only.

Observed:

- positive cases held: `0`;
- true hits lost by shadow gate: `0`;
- baseline false hits before shadow gate: `8`;
- baseline false hits after shadow gate: `0`.

Live Aio2 audit:

```text
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result: passed with existing warnings only.

Observed:

- active rows: `472`;
- trigger rows: `44`;
- projected rows: `43`;
- corpus cases: `14`;
- negative controls: `8`;
- baseline/shadow R@10: `0.857`;
- MRR: `0.786`;
- positive cases held: `0`;
- true hits lost by shadow gate: `0`;
- baseline false hits before shadow gate: `21`;
- baseline false hits after shadow gate: `0`.

## Verdict

`DESIGN-PLAN-ONLY / PRODUCTION-ENFORCE-HOLD-NO-GO`

The evidence is now strong enough to design a production-review packet. It is
not authorization to implement or enable production `enforce_hold`.

## Review Packet Purpose

The next packet should answer a narrow question:

```text
Is the current pre-policy hold simulation evidence sufficient for an owner to
review a future production implementation proposal?
```

It should not answer:

```text
Should production enforce_hold be enabled now?
```

The review packet is therefore a board-visible evidence bundle and decision
interface, not a runtime approval.

## Proposed Packet Identity

Suggested schema id:

```text
agent_bridge.memory.trigger_recall.pre_policy_hold.production_review_packet.v0
```

Suggested status values:

| Status | Meaning |
|---|---|
| `review_packet_ready_no_production_go` | evidence bundle is coherent, but production remains blocked |
| `blocked_missing_evidence` | one or more required evidence lines are absent |
| `blocked_stale_evidence` | required evidence is not from the current head/install |
| `blocked_boundary_regression` | any safety boundary regressed |
| `owner_decision_required` | packet is ready for owner review but cannot self-approve |

## Required Packet Fields

The production-review packet should include:

- exact repo head and `origin/master` hash;
- installed binary path, size, sha256, and deploy/rollout document reference;
- latest `doctor --json` summary;
- repeatable smoke command and result summary;
- portable Stage-2 fixture command and result summary;
- live Aio2 audit command and result summary;
- board post ids for install, stale-MCP closeout, runtime smoke, and repeatable
  smoke;
- memory keys for the same evidence;
- exact approved simulation implementation commit;
- regression anchor:
  `aio2_trigger_recall_baseline_acceptance_shadow_20260623`;
- explicit boundary booleans:
  - `default_memory_search_unchanged=true`;
  - `production_enforce_hold_authorized=false`;
  - `non_niche_exposure=false`;
  - `memory_writes=false`;
  - `graph_writes=false`;
  - `semantic_retrieval=false`;
  - `graph_retrieval=false`;
  - `reindex=false`;
  - `coactivation_for_withheld_hits=false`;
- rollback and operator-disable references;
- open blockers before any implementation proposal.

## Required Evidence Matrix

| Evidence | Current State | Required For Review Packet |
|---|---|---|
| mainline sync | `7cd8292` current | exact head and clean status |
| installed binary smoke | pass | repeatable command output |
| portable Stage-2 fixture | pass | command output and thresholds |
| live Aio2 audit | pass on 2026-06-23 | command output plus freshness note |
| board visibility | thread 105 posts through `#2522` | packet post id and parent refs |
| default search boundary | unchanged | explicit statement and falsifier |
| production hold | unauthorized | explicit NO-GO |
| raw payload redaction | pass | no raw query/key/content/scope leaks |
| rollback | env-disable path named | exact disable/revert mechanism |

## Hard NO-GO Conditions

The packet must remain NO-GO for production implementation if any condition is
true:

- `HEAD != origin/master`;
- installed binary hash does not match the packet;
- `doctor --json` reports stale active MCP processes for the binary under test;
- repeatable smoke fails;
- portable Stage-2 fixture fails;
- live Aio2 audit fails or is older than the packet freshness window;
- any positive case is held;
- any true hit is lost by the shadow gate;
- baseline false hits after shadow gate are nonzero;
- any raw query, key, content, or exact local scope leaks;
- any path reports `memory_search_mcp_called=true`;
- any path writes memory, graph edges, coactivation, or indexes;
- any default `memory_search` behavior, schema, or ordering changes;
- reviewer/owner approval is missing or does not name an exact implementation
  commit and approved mode.

## Freshness Rule

For the first review packet, evidence should be same-day and same-head:

```text
packet date = 2026-06-23
repo head = origin/master at packet creation
installed binary = current installed binary at packet creation
```

If the repo advances or the installed binary changes, rerun:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
git diff --check
```

## Planned Packet Sections

The next docs-only packet should use this outline:

1. `Verdict`: `REVIEW-PACKET-READY-NO-PRODUCTION-GO` or blocked status.
2. `Evidence Index`: commits, files, posts, memories, commands.
3. `Runtime Surface`: profile, tool count, Niche visibility, active profile
   hiding behavior.
4. `Smoke Results`: four-path repeatable smoke summary.
5. `Eval Results`: portable fixture plus live Aio2 audit.
6. `Boundary Table`: every side effect and default-search invariant.
7. `Open Blockers`: what still prevents production `enforce_hold`.
8. `Owner Decision Stub`: exact fields an owner would need to fill later.
9. `Rollback`: disable/revert plan.
10. `Next Slice`: allowed follow-up, still docs/review only unless separately
    approved.

## Next Allowed Slice

Create the production-review packet as a docs-only artifact.

Allowed:

- aggregate current evidence into the packet;
- cite exact command outputs and board/memory refs;
- mark production `enforce_hold` as blocked;
- prepare an owner decision stub with blank approval fields.

Forbidden:

- implementing production `enforce_hold`;
- changing default `memory_search`;
- promoting Niche tools into compact/essential profiles;
- adding hidden parameters to default `memory_search`;
- writing memory or graph state;
- changing indexing, tokenizer, semantic retrieval, or graph retrieval;
- treating this design plan as owner approval.
