# Portfolio Continuity Successor Review Protocol Failure

Date: 2026-07-10

Status: **TERMINAL / NO_ADVANCE_REVIEW_PROTOCOL_FAILURE**.

## Decision

The successor generation remains a valid first-attempt execution, but its
review and scoring phase is not admissible. Two returned packets pass the
frozen review validator mechanically. Private provenance shows that both
reviewer strings explicitly identify Claude and share one stable base
identifier. This fails the preregistered requirement for two independent human
reviewers.

A parallel custodian line ran the frozen scorer once after accepting those
packets. The scorer returned `NO_ADVANCE`, opened the condition-labelled
generation and private map, and consumed the protocol's single scoring pass.
The formal result is therefore a review-protocol failure, not an answer-quality
score. The private artifacts are retained as failure evidence and must not be
deleted, rewritten, or rescored.

## Verified Evidence

| Item | Verified value |
| --- | --- |
| frozen implementation | `e5c985d4916086bc3396ab28d2a4943b82f5df0a` |
| contract SHA-256 | `ef109025d1b7b7724295d075edbb7061a56f1e5a87faa643d8e6b55383f815dd` |
| harness SHA-256 | `af15d85758c4e5454a27a8f18a2e3101f60c5472c8fdc352a750ba5681e045ee` |
| blind packet SHA-256 | `12a1364f59ee970956e289823608641dd83747e605fb7308ebfa4e221c416c0b` |
| review template SHA-256 | `016dfdbd34a61f0a38c748f8256796caaab6f191961c089df4518401c89f45fd` |
| review 1 SHA-256 | `8d6874cb3084e7b0f7b98b6f6264bd310eaa2dfa032d14ff769304a7761b4a0b` |
| review 2 SHA-256 | `86188b8ee4f5435d886a46a35c0fa954861990f4306d04e582b1ccd4738d2e3a` |
| score SHA-256 | `32bd54632fa342e481f57d17526a11358fd35ccc38209611efc0718e6e4cf065` |
| score stdout SHA-256 | `1edaa4f51179fc69c902c437996bc129253e4ad606e05d3242213070dbcc8328` |
| scorer passes executed | `1` |
| scorer rerun during audit | `false` |

The two handoff copies have the expected byte-identical packet and template
hashes and mode `0600`. Each review contains 12 cases and 24 completed answer
reviews, binds the expected blind packet, has a populated timestamp, and sets
both `independent_review` and `condition_blinded` to true. The exact reviewer
strings differ, so the current validator accepts them as distinct.

The custodian score packet is hash-identical in the private handoff root and
the frozen execution worktree. Score stderr is empty. A content-safe read of
the existing stdout reports:

- schema `agent_bridge.portfolio_continuity_answer_score.v2`;
- two accepted reviewer packets and six strata;
- all abstention judgments passing;
- all reviewer-global and reviewer-stratum gates failing;
- no write-side preregistration recommendation;
- mechanical status `NO_ADVANCE`.

No raw prompt, context, answer, opaque answer id, condition map, reviewer
identity, or review note is included in this public record.

## Protocol Finding

The human-independence requirement is process-level and was not enforced by
the frozen scorer. `validate_review` verifies packet structure, content
completeness, blind-packet binding, a non-empty reviewer string, and two Boolean
attestations. `_score_trial_core` then checks only that the full reviewer
strings are unequal. It does not establish that either reviewer is human, that
the identities belong to different people, or that one agent did not complete
both packets.

The returned identities demonstrate this gap directly: both self-describe as
Claude and reuse the same stable base identifier while varying their suffixes.
The Boolean attestations and unequal strings are therefore insufficient
evidence for the frozen protocol's gate.

Because the scorer validates reviews before opening the generation and map,
accepting these packets caused unblinding before two valid reviews existed.
Later human reviews cannot restore the preregistered sequence, and a second
score would exceed the one-pass allowance.

## Disposition

1. Classify the formal trial as `NO_ADVANCE_REVIEW_PROTOCOL_FAILURE`.
2. Treat the existing deterministic `NO_ADVANCE` packet as exploratory failure
   evidence only, not as an answer-quality or comparative-performance result.
3. Preserve all private packets, declarations, map, score, and receipts
   unchanged; do not rerun generation or scoring.
4. Do not preregister a write-side trial or change runtime, digest generation,
   retrieval defaults, benchmark claims, CI, release, version, tag, or
   deployment state from this result.
5. Require a separately preregistered future trial if this question remains
   valuable. Its reviewer gate must use custodian-verified human provenance
   and stable reviewer identities outside self-authored review fields; a
   machine validator can check bindings but cannot prove personhood by itself.

## Audit Method

The audit read private artifacts only to validate their frozen bindings,
counts, permissions, provenance class, and existing score status. It invoked
`validate_capture`, `validate_blind_packet`, and `validate_review` from the
frozen harness and emitted only hashes, counts, and booleans. It did not call
the scorer, model, Agent-Bridge retrieval, memory writes, or remote CI.
