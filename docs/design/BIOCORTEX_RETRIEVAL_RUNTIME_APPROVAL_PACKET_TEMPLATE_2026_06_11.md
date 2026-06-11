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

Generate a current preview packet with:

```bash
cargo run -p ab-bridge --no-default-features \
  -- bio-cortex retrieval-approval-packet --json
```

The preview command is read-only. It may fill evidence fields supplied by CLI
arguments, but it always keeps approval state disabled.

For a reviewer-facing bundle with forum and memory templates, use:

```bash
scripts/prepare-biocortex-retrieval-approval-review.sh \
  --verification-log /tmp/biocortex-retrieval-shadow-verify.log \
  --reviewer "<human reviewer>"
```

That script writes local review-prep files only. It does not post to forum,
write memory, approve runtime influence, or change retrieval behavior.

Required safety fields:

- `approval_state=not_approved` until an explicit human decision changes it;
- `default_decision=keep_shadow_only`;
- `runtime_adapter_approved=false`;
- `writes_approval=false`;
- `approval_writes_allowed=false`;
- `default_search_order_change_allowed=false`;
- `requires_separate_human_approval=true`;
- `agent_technical_attestation.can_authorize_runtime_influence=false`;
- `human_authorization.status=not_authorized`;
- `human_authorization.can_be_replaced_by_agent_attestation=false`;
- `kill_switch_required=true`;
- `rollback_required=true`.

The agent may provide a technical attestation because it can inspect retrieval
behavior and memory impact more directly than the human reviewer. That
attestation is advisory and cannot replace human authorization of trust-boundary
scope.

Current allowed technical decisions are `approve_continue_design`, `approve`,
`reject`, `defer`, and `technical_review_pending`. Only
`approve_continue_design` is valid for continued design while the human
authorization scope remains `none`.

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
- agent technical attestation: attestor, decision, and summary;
- human authorization scope, defaulting to `none` until the human explicitly
  grants a wider scope.

## Review Rules

Passing metrics are not enough to approve runtime influence. Offline gate
success, shadow telemetry success, acceptance corpus success, or this template
being filled out must leave:

```json
{"runtime_adapter_approved": false}
```

A valid approval must combine an agent technical attestation with a separate
human authorization that explicitly names the reviewed implementation commit
and the authorized scope. Until then, BioCortex remains a read-only side signal
and the default `memory_search` order must stay unchanged.
