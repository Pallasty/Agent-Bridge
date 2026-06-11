# BioCortex Retrieval Runtime Approval Workflow

Date: 2026-06-11

## Purpose

This workflow prepares evidence for a future human review of BioCortex runtime
retrieval influence. It does not approve runtime influence and does not change
`memory_search`.

The default state remains:

```json
{
  "approval_state": "not_approved",
  "agent_attestation_can_replace_human_authorization": false,
  "runtime_adapter_approved": false,
  "approval_writes_allowed": false,
  "default_search_order_change_allowed": false
}
```

## Two-Layer Approval Model

The agent is the first technical user of AB memory retrieval and can inspect
details that are not fully visible to the human reviewer. Therefore the packet
must separate two judgments:

- `agent_technical_attestation`: the agent reviews evidence, retrieval impact,
  failure behavior, latency, rollback, and memory-search risk. This can
  recommend approve, reject, or defer, but it cannot authorize runtime influence.
- `human_authorization`: the human owner authorizes the trust-boundary scope.
  The human does not need to inspect every raw memory row; the human authorizes
  a scope based on the agent's technical summary and evidence packet.

Agent attestation cannot replace human authorization. Human authorization does
not rewrite technical evidence.

## Review Preparation

1. Run the verification bundle on the target host:

   ```bash
   AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs \
   scripts/verify-biocortex-retrieval-shadow.sh \
     2>&1 | tee /tmp/biocortex-retrieval-shadow-verify.log
   ```

2. Generate the review-prep bundle:

   ```bash
   scripts/prepare-biocortex-retrieval-approval-review.sh \
     --reviewer "<human reviewer>" \
     --agent-attestor "codex" \
     --agent-attestation-decision "technical_review_pending" \
     --human-authorization-scope "none" \
     --verification-log /tmp/biocortex-retrieval-shadow-verify.log \
     --memory-key "<future memory key>" \
     --forum-decision-post-id "<future forum post id>"
   ```

3. Inspect `approval-packet-preview.json`. It must still say:

   - `approval_state=not_approved`;
   - `runtime_adapter_approved=false`;
   - `writes_approval=false`;
   - `approval_writes_allowed=false`;
   - `default_search_order_change_allowed=false`;
   - `ready_for_human_approval_review=false`.
   - `agent_technical_attestation.can_authorize_runtime_influence=false`;
   - `human_authorization.status=not_authorized`.

4. Post the generated `forum-post-template.md` to the forum only after a human
   reviewer has inspected the packet and any missing evidence.

5. Save the generated `memory-note-template.md` as memory only after the forum
   post id is known.

## Human Approval Rule

No script in this workflow can approve runtime retrieval influence. A valid
technical attestation can only say whether the agent recommends approve,
reject, or defer on technical grounds. A valid human authorization must be a
separate decision that explicitly names the reviewed implementation commit and
the authorized scope, such as `continue_design`, `opt_in_experiment`, or
`default_retrieval_influence`.

Until that decision exists, BioCortex remains a read-only side signal.
