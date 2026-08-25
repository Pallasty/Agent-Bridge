# R7 Resident Xiao Shu v0

Date: 2026-08-25 (America/Los_Angeles)

Status: M0/M1 source, test, and owner-local live gates passed; deployment and
installed-binary verification follow in this record. Owner usefulness label
remains explicitly unknown until the owner labels installed use.

## Product decision

Agent-Bridge is the continuity and governance runtime for one persistent
owner-local subject, Resident Xiao Shu. A Codex/model process is a disposable
cognition provider; it is not the identity, durable memory authority, task
truth authority, or a body. The north star is **persistent subject,
intermittent cognition, reversible bodies**.

R7 proves only one explicit, one-shot, advisory cognition slice. It introduces
no scheduler, daemon, service, autostart, unattended wake, effectful tool or
system authority, automatic memory promotion, or expression execution.

## Delivered slice

- An AB-owned identity manifest fixes subject and lineage IDs, durable
  principles, owner posture, manifest revision, capability baseline, and AB
  provenance independently of model/session/process identifiers.
- `agent-bridge resident cognition` accepts a bounded owner event and opaque
  `event_id`; dry-run exposes the launch contract without provider or state.
- A deterministic wake ID plus private `create_new` journal provides replay
  refusal across restarts. A non-blocking subject fence spans continuity read,
  provider execution, validation, and commit.
- `codex exec` receives the prompt only on stdin and the result through a
  strict schema. The default is `gpt-5.6-luna`, low effort, and a 120-second
  deadline.
- User config, rules, hooks, MCP/plugins/apps, shell/unified exec/code mode,
  browser/computer/image, and multi-agent features are requested disabled
  under strict config. The sandbox is read-only, approval is never, rollout is
  ephemeral, environment inheritance is allowlisted, output sizes are bounded,
  and the complete process group is reaped.
- Codex JSONL is audited fail-closed. Only lifecycle, reasoning, agent-message,
  and the exact known “code mode disabled/fail closed” diagnostic are admitted;
  tool, other error, malformed, or unknown events fail the wake.
- Strict result and wake/subject binding precede a verified completion receipt.
  Invalid output, identity mismatch, provider/tool-event failure, or timeout
  records a non-green failure and never advances the sleep digest.
- Durable receipts contain the event ID/hash, provider provenance and bounded
  intent/digest. Raw owner event text and full provider transcript are absent.

The receipt is deliberately narrow. It does not prove that Codex transport
performed no auth/home reads or provider-network traffic; those are required
to invoke the provider. It records requested feature/sandbox bounds, audited
model-facing event types, schema and identity binding, timing/hashes, and child
exit. Provider summaries remain `provider_claim`; owner acceptance remains
`unknown`.

## Automated verification

- `ab-agent resident_codex`: 7 passed. Coverage includes invocation flags and
  stdin privacy, feature disablement, read-only/ephemeral contract, host-lock
  refusal, deadline process-group cleanup, stdout bounds, malformed final JSON,
  and fail-closed provider tool events.
- `ab-bridge resident_`: 9 passed. Coverage includes dry-run, two fresh
  invocation continuity recovery, raw-event exclusion, identity mismatch,
  deterministic replay refusal, single-writer concurrency, private journal
  reopen, and failure-no-advance behavior.
- `ab-bridge` no-default-features debug binary build passed.
- `git diff --check` passed. Repository-wide `cargo fmt --check` remains blocked
  only by pre-existing drift in `avatar_cortex.rs` and `avatar_health.rs`; all
  R7 Rust files were formatted directly.

## Owner-local live acceptance

Acceptance used an isolated XDG state root and real `codex-cli 0.149.1`.

1. Two separate AB/Codex processes completed in 21,049 ms and 20,350 ms. The
   second retained `agent-bridge:resident:xiaoshu` and recovered the first
   sleep-digest hash and concern without the earlier provider process.
2. Replaying the second `event_id` failed with `resident_wake_duplicate` in
   0.02 seconds before provider launch.
3. While a third real provider held the subject fence, a different event
   failed with `resident_wake_concurrent` in 0.02 seconds; the holder completed
   normally.
4. Hardening initially rejected a live result because JSONL contained an
   internal diagnostic event. A content-free probe identified one hooks event
   plus the code-mode-host fail-closed diagnostic. Hooks/code mode were then
   explicitly disabled; only the exact fail-closed diagnostic was admitted.
   The rejected wake was recorded `not_verified` and did not advance state.
5. The hardened retry completed in 17,758 ms with five audited events, zero
   provider tool events, one explicit fail-closed diagnostic, and zero stderr.
6. The final enriched-identity wake completed in 20,402 ms with the same
   subject, three AB-owned durable principles, owner posture, AB provenance,
   recovered compact continuity, zero tool events, and one fail-closed
   diagnostic.

Final isolated evidence contained five `cognition_completed/verified` events
and one intentional `cognition_failed/not_verified` event. The final receipt
reported zero provider tool events. Full-text search found none of the live
owner-event strings in the state root. The journal contained six private wake
records, including the failed hardening wake. No resident Codex child or
temporary provider directory remained. The final isolated SQLite SHA-256 was
`4f69aa9bd615d705670070e7b643bfcde79357a814b05b582f5dd8dd2f7b5a75`.

## Remaining decision

This establishes technical M1, not autonomous residence or product value.
After installed use, the owner should label the behavior **useful**,
**neutral**, **distracting**, or **harmful**. Until that label, R7 does not
admit M2 scheduling or any authority/body expansion.
