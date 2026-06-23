# Trigger Recall Pre-Policy Hold Production Implementation Proposal Design

Date: 2026-06-23

Scope: docs-only design for a future production implementation proposal after
the production-review packet and owner decision record.

This document does not implement production `enforce_hold`, does not authorize
production behavior, does not change default `memory_search`, does not promote
Niche surfaces, and does not write memory, graph, index, semantic, or
coactivation state.

## Verdict

`DESIGN-PROPOSAL-ONLY / IMPLEMENTATION-NO-GO`

The evidence chain is strong enough to define the minimum acceptable shape of a
future implementation proposal. It is still not authorization to write runtime
code.

Current approval state:

```text
production_enforce_hold_authorized=false
default_memory_search_change_authorized=false
non_niche_exposure_authorized=false
```

## Inputs

Accepted evidence:

- `7cd8292 test(memory): add pre-policy hold runtime smoke script`;
- `0bf9662 docs(memory): add pre-policy hold production review packet`;
- `a6f9e87 docs(memory): record pre-policy hold owner decision`.

Board references:

- `#2522`: repeatable operator smoke command;
- `#2524`: production-review packet;
- `#2525`: owner decision record.

Standing command gate:

```text
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
```

The standing command verifies:

- target Niche tool visible in explicit all profile;
- held path does not call store FTS by default;
- accepted path calls store FTS directly and remains redacted;
- missing approval and operator disabled paths fail open;
- no MCP `memory_search`;
- no memory writes;
- no graph writes;
- no semantic or graph retrieval;
- no reindex;
- no production `enforce_hold`.

## Proposed Future Proposal Identity

A later implementation proposal, if requested, should use a separate schema:

```text
agent_bridge.memory.trigger_recall.pre_policy_hold.production_implementation_proposal.v0
```

Suggested status values:

| Status | Meaning |
|---|---|
| `proposal_ready_no_code_go` | proposal is coherent but implementation remains blocked |
| `blocked_missing_owner_authorization` | no owner packet authorizes implementation |
| `blocked_stale_evidence` | required evidence is not at current head/install |
| `blocked_boundary_regression` | a default-search or side-effect invariant regressed |
| `blocked_missing_rollback` | disable/revert path is absent or untested |

## Minimum Proposed Runtime Shape

The first future implementation proposal must stay default-off and explicit:

| Layer | Proposed Shape |
|---|---|
| default `memory_search` | unchanged; no hidden parameter |
| profile exposure | Niche/all profile only unless a later tool-surface review says otherwise |
| mode | `production_enforce_hold_candidate`, not enabled by default |
| runtime env | `AB_TRIGGER_RECALL_ENFORCE_HOLD_OPT_IN=1` required |
| kill switch | `AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1` fails open |
| per-call gate | `per_call_opt_in=true` required |
| scope | exact local `project:/abs/path`, `scope_mode=local_only` |
| retrieval mode | `fts` only |
| response | object status, never bare `[]` for held queries |

The proposal should build on the already verified simulation behavior, but must
not silently convert simulation into production behavior. It needs a new owner
packet naming exact code and mode.

## Candidate Code Surface

No code is authorized now. If later authorized, the implementation proposal
should name exact files and expected changes:

| File | Future Proposal Should Name |
|---|---|
| `crates/bridge/src/trigger_recall_opt_in.rs` | pure production-candidate option type, validator, response builder, tests |
| `crates/bridge/src/mcp_tools.rs` | Niche MCP wrapper, schema, all-profile registration, redaction tests |
| `scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh` | update or extend only if the smoke remains read-only and default-off |
| `docs/reports/goal-c-u/...` | implementation report and exact evidence packet |

No store crate changes are part of the first acceptable proposal unless a later
owner packet explicitly authorizes them.

## Approval Packet Required Before Code

Before code can be written, a separate owner packet must exist with:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold.production_implementation_approval.v0",
  "owner_decision": "approve_production_implementation_candidate_code_only",
  "approved_mode": "production_enforce_hold_candidate",
  "approved_implementation_branch": "TBD",
  "approved_implementation_commit": "TBD-after-candidate-exists",
  "approved_runtime_surface": "Niche/all-profile explicit opt-in only",
  "default_memory_search_change_authorized": false,
  "production_enforce_hold_runtime_enable_authorized": false,
  "rollback_required": true,
  "expires_at": "TBD"
}
```

Important boundary: even a future code-only approval should not enable
production runtime behavior. Runtime enablement needs a separate post-code
review packet naming the exact candidate commit.

## Required Pre-Code Verification

Immediately before any future code proposal is accepted, rerun:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
git diff --check
```

Required thresholds:

| Metric | Required |
|---|---:|
| doctor fails | `0` |
| stale MCP processes for installed `.real` | `0` |
| repeatable smoke status | `passed` |
| true hits lost by shadow gate | `0` |
| positive cases held | `0` |
| baseline false hits after gate | `0` |
| MCP `memory_search` called by smoke | `false` |
| raw query/key/content/scope leak | `false` |

## Required Implementation Tests

A future implementation commit must add or preserve tests for:

- production candidate tool stays Niche/all only;
- missing approval fails open;
- operator disable fails open;
- held path does not call store FTS by default;
- accepted path preserves baseline order;
- count-audit path returns count/order hash without visible withheld hits;
- default `memory_search` schema and behavior remain unchanged;
- no MCP `memory_search` call;
- no memory writes;
- no graph writes;
- no coactivation for withheld hits;
- no semantic or graph retrieval;
- held response is an object with status, not a bare empty array.

## Rollback Requirements

The future proposal must include both:

```text
AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1
```

and installed-binary rollback:

```text
cp <recorded-agent-bridge.real-backup> /home/pallasting/.local/bin/agent-bridge.real
/mcp reconnect
```

The disable path must fail open to baseline behavior and report
`operator_disabled`.

## Explicit Non-Goals

Still not allowed:

- production runtime enablement;
- default `memory_search` behavior, schema, or order changes;
- compact/essential exposure;
- hidden parameters on default `memory_search`;
- non-FTS modes;
- memory writes;
- graph writes;
- reindexing;
- tokenizer changes;
- semantic retrieval;
- graph retrieval;
- coactivation for withheld hits.

## Next Gate

Allowed next:

- write a docs-only production implementation approval-packet schema or
  checklist;
- or pause for explicit owner review before any further production-lane work.

Blocked until a new owner packet exists:

- candidate code implementation;
- runtime enablement;
- default retrieval changes.
