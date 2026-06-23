# Trigger Recall Pre-Policy Hold Stage 2 Review

Date: 2026-06-23

Review target:
- Candidate branch: `codex/trigger-pre-policy-hold-simulation-candidate`
- Candidate worktree: `/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate`
- Candidate commit: `2ceeef974066d382f69a0f2774ea08e452ca5252`
- Stage-1 authorization base: `87d709a`

Verdict: `ACCEPTED-PENDING-AIO2-AUDIT-EVIDENCE`

This review accepts the candidate shape through the narrow Stage-2 checklist, but does not approve merge, deploy, default retrieval changes, or production `enforce_hold`. The remaining blocker is the wider aio2 baseline acceptance audit, which cannot complete on this Mac corpus because the required key is absent.

## Diff Audit

The candidate diff is limited to the Stage-1 authorized files:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-simulation.md`

Diff from `87d709a..2ceeef9`:

- 3 files changed
- 1233 insertions
- 3 deletions

No default `memory_search` code path or public production hold behavior was approved by this review.

## Accepted Candidate Shape

The candidate implements:

- pure builder `trigger_recall_opt_in_pre_policy_hold_simulation`;
- approval packet validation for `agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0`;
- candidate env gates `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN` and `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE`;
- candidate-only MCP tool `trigger_recall_opt_in_pre_policy_hold_simulation`;
- `Tier::Niche` registration, present in `all`, absent from Codex essential;
- held-query default path returning explicit object status, not bare `[]`;
- no store FTS call for held queries unless `include_baseline_counts=true`;
- count-audit path limited to redacted count/order hash;
- accepted/fail-open paths using direct store FTS, not the MCP `memory_search` tool;
- no query, key, content, or scope echo in output;
- `may_change_default_memory_search_now=false`;
- `may_implement_enforce_hold_now=false`;
- `stage2_approval_required_before_merge_or_deploy=true`.

## Verification Run

All commands were run in `/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate` at `2ceeef974066d382f69a0f2774ea08e452ca5252`.

Passed:

```text
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
```

Result: 33 passed.

```text
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
```

Result: 27 passed.

```text
cargo check -p ab-bridge --lib
```

Result: passed with existing warnings.

```text
cargo check -p ab-bridge --all-targets
```

Result: passed with existing warnings.

```text
git diff --check
git diff --check 87d709a..HEAD
```

Result: passed.

The candidate worktree remained clean after verification.

## Blocking Evidence Gap

The wider aio2 baseline acceptance audit still fails on this Mac node:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Result:

```text
Error: "aio2_lswr_g21_g22_apply_writer expected key missing: lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620"
```

This reproduces the candidate author's reported blocker. Because the audit depends on a corpus key absent from this local store, this review cannot honestly certify the wider acceptance anchor.

## Decision

Allowed now:

- keep the candidate branch/worktree for review;
- use this review as evidence that the narrow Stage-2 code shape and focused tests passed;
- rerun the aio2 audit on a corpus-bearing node or repair the audit fixture/corpus contract with explicit owner approval.

Not allowed yet:

- merge `2ceeef9` to master;
- deploy this tool;
- expose it outside `Tier::Niche`;
- change default `memory_search`;
- enable production `enforce_hold`;
- claim final Stage-2 approval.

The next valid closeout is a follow-up Stage-2 packet that names `2ceeef974066d382f69a0f2774ea08e452ca5252` again and includes passing aio2 baseline audit evidence, or a documented owner decision that replaces that audit requirement.
