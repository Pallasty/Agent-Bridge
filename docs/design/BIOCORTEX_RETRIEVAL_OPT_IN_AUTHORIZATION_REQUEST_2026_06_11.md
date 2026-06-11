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
  --reviewer "<human reviewer>" \
  --memory-key "<future memory key>" \
  --forum-decision-post-id "<future forum post id>"
```

The generated packet schema is:

```json
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
  "approval_state": "not_approved",
  "authorization_state": "requested_not_granted",
  "request_scope": "opt_in_experiment",
  "implementation_allowed": false
}
```

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
