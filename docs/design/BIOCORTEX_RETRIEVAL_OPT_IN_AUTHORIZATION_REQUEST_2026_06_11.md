# BioCortex Retrieval Opt-In Authorization Request

Date: 2026-06-11

## Purpose

This request packet prepares a future human review for `opt_in_experiment`
authorization. It is not approval state and does not permit implementation by
itself.

Generate a local review bundle with:

```bash
AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs \
scripts/prove-biocortex-retrieval-runtime-boundary.sh \
  --out-dir /tmp/biocortex-retrieval-runtime-proof

scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh \
  --runtime-proof-summary /tmp/biocortex-retrieval-runtime-proof/proof-summary.json \
  --runtime-trial-review-packet /tmp/biocortex-runtime-trial-review-packet.json \
  --order-diff-packet /tmp/biocortex-order-diff-packet.json \
  --reviewer "<human reviewer>" \
  --memory-key "<future memory key>" \
  --forum-decision-post-id "<future forum post id>"
```

The static request template starts as:

```json
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
  "approval_state": "not_approved",
  "authorization_state": "requested_not_granted",
  "request_scope": "opt_in_experiment",
  "implementation_allowed": false
}
```

When generated against the current opt-in plan fixture, the request reflects the
already recorded implementation authorization with
`approval_state=opt_in_implementation_authorized` and
`authorization_state=authorized_for_opt_in_implementation`. It still preserves
`runtime_adapter_approved=false`, `default_search_order_change_allowed=false`,
and `writes_approval=false`.

The runtime trial review packet is required post-implementation evidence. The
request generator copies only its safe summary fields under
`evidence.runtime_trial_review_packet`; it does not include raw query text,
candidate keys, content, side-signal rows, or the raw review packet.

The order-diff packet is optional hash-only evidence. When provided, the
request generator copies only safe booleans and rank-summary fields under
`evidence.order_diff_packet`: diff readiness, hash comparability, changed flags,
expected-key rank delta, returned-order source, and unavailable-metric
sentinels. It does not include raw order keys, raw query text, content, raw
side-signal rows, raw source packets, or approval state changes.

## Scope Requested

This request asks for permission to implement an FTS-only, per-call opt-in
experiment design. If approved later, the implementation must still be reviewed
before use.

The request does not ask for:

- default retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- `runtime_adapter_approved=true`;
- `default_search_order_change_allowed=true`.

## Valid Human Decision

A valid authorization must be a separate human decision and must explicitly
include:

- `opt_in_experiment`;
- the implementation commit under review;
- no default retrieval influence;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE` remains the kill switch.

Without that separate human decision, this request remains review preparation
only.

## Current Decision

The current human decision is recorded separately:

- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_2026_06_11.md`
- `docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json`

That decision authorizes `opt_in_experiment` implementation work only. It does
not authorize default retrieval influence.
