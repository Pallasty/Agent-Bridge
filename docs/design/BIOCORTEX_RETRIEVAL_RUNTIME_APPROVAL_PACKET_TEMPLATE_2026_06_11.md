# BioCortex Retrieval Runtime Approval Packet Template

Date: 2026-06-11

## Purpose

This is a template for a future human review packet. It is not an approval
record and must not enable runtime retrieval influence by itself.

Default state:

```json
{
  "approval_state": "not_approved",
  "runtime_adapter_approved": false,
  "approval_writes_allowed": false,
  "default_search_order_change_allowed": false
}
```

Use this packet only after the shadow/advisory implementation has already
passed the verification bundle and the reviewer is deciding whether a separate
runtime adapter design may change default retrieval behavior.

## Required Packet Fields

The machine-readable packet should follow the companion fixture:

- `docs/design/fixtures/biocortex-retrieval-runtime-approval-packet-template.json`

Required safety fields:

- `approval_state=not_approved` until an explicit human decision changes it;
- `default_decision=keep_shadow_only`;
- `runtime_adapter_approved=false`;
- `writes_approval=false`;
- `approval_writes_allowed=false`;
- `default_search_order_change_allowed=false`;
- `requires_separate_human_approval=true`;
- `kill_switch_required=true`;
- `rollback_required=true`.

## Evidence Requirements

Before any packet can be considered for approval, it must include concrete
evidence for every item below:

- target host, branch, commit, and reviewer identity;
- output from `scripts/verify-biocortex-retrieval-shadow.sh`;
- current corpus and hard holdout gate summaries for `candidate-strong`;
- live MCP default-disabled result showing `status=runtime_disabled` without
  `AB_BIOCORTEX_RETRIEVAL_SHADOW=1`;
- kill-switch proof showing `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` forces
  baseline-only behavior even when the enable flag is set;
- latency evidence for both the side-signal surface and the default
  `memory_search` path;
- exact call site where any future retrieval ordering would change;
- fail-open behavior when BioCortex is absent, slow, or errors;
- rollback command and operator kill switch;
- forum decision post id and memory key linking the final evidence packet.

## Review Rules

Passing metrics are not enough to approve runtime influence. Offline gate
success, shadow telemetry success, acceptance corpus success, or this template
being filled out must leave:

```json
{"runtime_adapter_approved": false}
```

A valid approval must be a separate human decision that explicitly says default
retrieval influence is allowed and names the reviewed implementation commit.
Until then, BioCortex remains a read-only side signal and the default
`memory_search` order must stay unchanged.
