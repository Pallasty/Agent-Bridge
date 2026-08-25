# R5 P1a first-capture failure and rollback

Capture date: 2026-08-25 (America/Los_Angeles)

## Activation evidence

- Installed source: `8ab8bdc6b619cbe35e7642c12bb27b4d13aceb9a`.
- Installed `.real` SHA-256:
  `80cc0ed3a95ec116009a7b0d8df86585a24a4e07ad39ebff75d986085a647b00`.
- Six current `.real` MCP children were observed after the Codex restart.
- The compact manifest exposed `session_finalize`,
  `practical_workflow_scorecard`, `embodiment_record`, and
  `embodiment_snapshot`.
- The public record schema allowed only `operation_receipt`. The first
  receipt snapshot read zero rows and excluded Event Spine, body telemetry,
  and write-lease state.

These observations satisfy the P1a collection prerequisites but remain
agent-reported runtime evidence rather than authenticated process identity.

## Outcome capture

The natural task was the qualification, dual-remote synchronization,
deployment, and runtime verification of the current Agent-Bridge source. The
first `session_finalize` attempt supplied a bare 64-hex evidence digest. The
validator requires the canonical `sha256:<64 lowercase hex>` form and rejected
the request with `invalid_sha256_digest`. A read immediately afterward
confirmed zero admitted outcome rows and zero receipt rows.

A transparent retry reused the same opaque outcome and environment IDs and
changed only the digest encoding. It inserted one immutable outcome with:

- status `achieved` and verification `verified/tests`;
- provenance `agent_reported`;
- acceptance `unknown` / `unavailable`;
- rollback `available`; and
- complete burden counts: one manual intervention, zero owner restatements,
  and zero repeated authorization prompts.

The read-only scorecard then reported one admitted record, one reported
verified/achieved result, complete burden coverage, and no persisted invalid
or conflicting row. The current ledger is not an attempt journal, so the
rejected request remains agent-reported capture evidence rather than a
reconstructable scorecard fact.

## Decision

P1a is **FAIL**. The frozen contract makes any invalid `session_finalize`
response observed during capture an immediate gate failure. The later valid
insert does not replace or erase that event.

The receipt lane is `insufficient_natural_sample`: no production
`BodyOperationEnvelope` was naturally produced, no receipt was written, and
no receipt was fabricated to populate the trial.

Apply the preregistered rollback by removing `embodiment_record` and
`embodiment_snapshot` from `CODEX_ESSENTIAL_DIRECT_EXTRAS`, rebuilding,
redeploying, restarting participating MCP clients, and confirming both names
are absent from the compact manifest. Keep the P0 ledgers and admitted outcome
for audit. This decision grants no executor, registry, lease, mutation,
automatic receipt, or authenticated owner/harness authority.
