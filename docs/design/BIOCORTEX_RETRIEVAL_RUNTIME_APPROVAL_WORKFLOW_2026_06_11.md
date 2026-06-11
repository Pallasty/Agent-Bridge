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
  "runtime_adapter_approved": false,
  "approval_writes_allowed": false,
  "default_search_order_change_allowed": false
}
```

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

4. Post the generated `forum-post-template.md` to the forum only after a human
   reviewer has inspected the packet and any missing evidence.

5. Save the generated `memory-note-template.md` as memory only after the forum
   post id is known.

## Human Approval Rule

No script in this workflow can approve runtime retrieval influence. A valid
approval must be a separate human decision that explicitly names the reviewed
implementation commit and says default retrieval influence is allowed.

Until that decision exists, BioCortex remains a read-only side signal.
