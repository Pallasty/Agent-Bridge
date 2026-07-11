# Portfolio Continuity Successor V3 Implementation Review

Date: 2026-07-10

Status: **INDEPENDENT REVIEW COMPLETED / FINDINGS REMEDIATED / FOLLOW-UP
PENDING / NOT EXECUTED**.

## Review Identity

```yaml
reviewer: claude-opus-4-8
cli: Claude Code 2.1.207
effort: high
workspace_commit: a9bb0c93fcfecc63761946f50c7275f78de8db23
workspace_private_data_present: false
model_turns: 8
raw_review_receipt_sha256: d14a534840810d0656757eb48b5523dbad5a654b40783272959a745073be1fd1
stderr_bytes: 0
capture_or_answer_generation: false
remote_ci: false
```

The reviewer ran in a clean detached worktree with only `Read`, `Glob`, and
`Grep`. It was instructed not to read `data/`, write files, run commands, use
MCP/web/external context, or evaluate private prompts or answers. The first
CLI launch failed before model invocation because the empty MCP configuration
shape was invalid; the corrected read-only invocation completed successfully.

## Verdict

The review returned `PASS` for the overall fail-closed decision path and found
no way to make a failing score advance or to open generation/map before two
provenance-bound reviews. It confirmed v3 schema/hash isolation from v2,
fixed reviewer slots, opaque forbidden-claim mapping, per-reviewer/per-stratum
all-gates, response/review byte identity, and receipt-before-unblind ordering.

It also reported two hardening findings. This lane treats the first as an
execution blocker because the preregistration claimed a stronger single-use
property than the implementation provided.

## Findings And Disposition

### 1. Operator-selected score claim path allowed replay

The initial implementation accepted `--score-claim`. Repeating `score` with a
different fresh claim and output path could create another `O_EXCL` file and
open the generation/map again. The original adversarial test covered only
reuse of the same path.

Disposition: **FIXED BEFORE EXECUTION**.

- remove the public score-claim path argument;
- derive one identity as SHA-256 of `score_claim_schema + NUL + contract_sha`;
- place it in the fixed ignored
  `data/portfolio-continuity-score-claims/` directory;
- bind the exact policy in contract `score_policy`;
- reject aliasing with any score input/output;
- test replay with a different output path.

### 2. Command bytes were hashed but not semantically validated

The initial receipt bound command bytes but trusted Boolean statements that
model and effort were pinned. A different command could be rehashed while the
receipt retained those fixed flags.

Disposition: **FIXED BEFORE EXECUTION**.

- require strict `agent_bridge.portfolio_continuity_answer_review_command.v3`
  JSON;
- bind slot, stdin request hash, absolute cwd, and zero context environment
  keys;
- validate the complete normalized Claude or Codex argv profile;
- require the exact model and Codex effort argument;
- forbid a Claude effort override when the frozen policy is CLI default;
- bind the receipt workspace-path hash to the command cwd;
- test a rehashed wrong-model command.

## Remaining Disclosed Risks

- Provider/model identity ultimately remains a custodian attestation rather
  than a provider-signed receipt.
- Session and usage hashes are provenance records, not independent identity
  proofs.
- Generation-time marker validation remains the guard against condition text
  leaking into answers; blind validation does not duplicate that scan.
- Current coverage guarantees make zero-token and empty-usefulness score
  denominators unreachable, but the arithmetic functions do not separately
  guard those impossible states.

None authorizes execution. The remediated source, contract, documentation, and
adversarial tests require a new frozen commit plus an independent follow-up
review before an execution decision.
