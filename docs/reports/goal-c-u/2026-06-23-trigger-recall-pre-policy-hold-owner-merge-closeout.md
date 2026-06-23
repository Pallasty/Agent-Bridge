# Trigger Recall Pre-Policy Hold Owner Merge Closeout

Date: 2026-06-23

Merge target:
- Candidate branch: `codex/trigger-pre-policy-hold-simulation-candidate`
- Candidate commit: `2ceeef974066d382f69a0f2774ea08e452ca5252`
- Mainline base before merge: `068f214`

Decision: `MERGED-BY-OWNER-OVERRIDE-WITH-AIO2-AUDIT-GAP-RECORDED`

The Stage-2 review previously landed as:

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-stage2-review.md`

That review accepted the narrow candidate shape but left final merge blocked on
the wider aio2 baseline acceptance audit. The audit still fails on this Mac node
because the local corpus is missing:

```text
lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620
```

The owner then explicitly authorized proceeding with the merge while aio2 is
unattended. This closeout records that the merge is based on owner override plus
Mac-side verification, not on passing aio2 audit evidence.

## Boundaries Preserved

This merge does not authorize:

- default `memory_search` changes;
- production `enforce_hold`;
- non-Niche exposure;
- deployment or installed-binary rollout;
- semantic retrieval or graph retrieval changes;
- memory writes;
- graph-edge writes.

The merged surface remains an opt-in, candidate-shaped simulation tool:

- `trigger_recall_opt_in_pre_policy_hold_simulation`
- `Tier::Niche`
- gated by `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN`
- disabled by `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE`
- requires explicit approval packet and per-call opt-in.

## Merge Conflict Resolution

The merge conflicted only in the source-file top-level constant/import regions:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`

Resolution kept both mainline approval-packet validator work and the candidate
pre-policy hold simulation work:

- `trigger_recall_enforce_hold_approval_packet_validator`
- `trigger_recall_opt_in_pre_policy_hold_simulation`

Both tools remain `Tier::Niche`.

## Verification

Run on mainline after conflict resolution:

```text
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
```

Result: 36 passed.

```text
cargo check -p ab-bridge --lib
```

Result: passed with existing warnings.

```text
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
```

Result: 27 passed.

```text
cargo check -p ab-bridge --all-targets
```

Result: passed with existing warnings.

```text
git diff --check
git diff --cached --check
```

Result: passed.

The aio2 audit gap remains recorded and should be rerun on a corpus-bearing node
when aio2 is attended again.
