# Correction Co-Surface LINK Review

Date: 2026-07-01
Host: `pallasting-ThinkBook-14-G5-IRH`
Worktree: `/Data/CascadeProjects/agent-bridge`
Scope: review closeout for the correction-to-original LINK lever

## Background

Forum post `#2647` proposed a correction/original LINK lever after the semantic
rebalance work showed that `w_fb` alone could not reliably surface corrections.
The key claim was that explicit graph links between active corrections and the
original memory they correct are a better retrieval primitive than a global
feedback weight.

That proposal was later implemented as PR #36:

```text
Merge commit: 5e8ae2f Merge pull request #36 from pallasting/claude/correction-cosurface-20260630
```

The branch is now an ancestor of current `origin/master`; it is not an open
unmerged branch.

## What Landed

PR #36 added two default-safe pieces.

A1, write path:

- `memory_save` auto-links out-of-tool correction rows with a `corrects` edge.
- The target is `related_keys[0]`, so `[target, extra_context...]` remains valid.
- Empty or missing first related key still skips auto-linking.

B1, read path:

- `memory_search` can co-surface active correction rows directly after an
  original row they correct.
- The behavior is gated by `AGENT_BRIDGE_CORRECTION_COSURFACE`.
- Default OFF keeps normal output byte-equivalent.
- Co-surfaced rows honor `exclude_kinds`, preserving the documented output
  contract for callers that exclude feedback.

## Review History

Post `#2682` found two blockers before merge:

- B1 inserted feedback rows after the main `exclude_kinds` filter.
- A1 required exactly one related key, despite the proposal using
  `related_keys[0]` as the target.

Post `#2686` records the fixes:

- B1 now passes `exclude_kinds` into `cosurface_corrections`.
- A1 now uses first-key target semantics and has regression coverage.

## Verification On Current Master

Current branch state:

```text
master == origin/master == 9be8012
origin/claude/correction-cosurface-20260630 is ancestor of origin/master
```

Merge status:

```sh
git rev-list --left-right --count origin/master...origin/claude/correction-cosurface-20260630
```

Result:

```text
49 0
```

Store-side A1 regression:

```sh
CARGO_BUILD_JOBS=1 cargo test -p ab-store \
  a1_memory_save_auto_links_corrects_edge_for_out_of_tool_correction \
  -- --nocapture
```

Result:

```text
test sqlite::tests::a1_memory_save_auto_links_corrects_edge_for_out_of_tool_correction ... ok
test result: ok. 1 passed; 0 failed
```

Bridge-side B1 regression:

```sh
CARGO_BUILD_JOBS=1 cargo test -p ab-bridge --no-default-features --lib \
  b1_cosurface_inserts_corrector_after_corrected_original \
  -- --nocapture
```

Result:

```text
test mcp_tools::tests::b1_cosurface_inserts_corrector_after_corrected_original ... ok
test result: ok. 1 passed; 0 failed
```

MCP lifecycle snapshot after the review:

```text
lifecycle_state=ready
readiness_status=ready
readiness_warnings=0
failing_tool_count=0
```

## Boundary

This review does not enable `AGENT_BRIDGE_CORRECTION_COSURFACE`, does not
backfill live correction edges, does not alter semantic/FTS ranking weights, and
does not deploy a new binary.

Remaining gated actions, if desired:

- Decide whether to enable `AGENT_BRIDGE_CORRECTION_COSURFACE` for an A/B window.
- Decide whether a one-time live-store correction-edge backfill is worth doing.
- Keep PR #32 semantic rebalance separate; it solves a different recall side and
  must remain owner-reviewed before merge/deploy.
