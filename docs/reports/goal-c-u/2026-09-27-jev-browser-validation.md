# Jev browser validation: plan and acceptance

Date: 2026-09-27. User authorization: after the Jev Ultrafast research, plan
validation goals, validate them, and implement the feasible outcomes.

Base: canonical `Pallasty/Agent-Bridge main` at
`6c4b1a9f332d8b9e9329f8d2914deed7db713453`, fetched and checked with
`git ls-remote` before creating this isolated worktree.
Branch: `codex/jev-browser-validation-20260927`.

Research source: `browser-use/jev-ultrafast` at
`1231850a0bf1a0c0341fe408ef1668dbbfdfac46`. The retained source manifest,
research report and offline probes are under
`/Data/session-archives/20260927-jev-ultrafast-research/`.

## Goal and decision gates

| Goal | Hypothesis and acceptance | Feasible outcome |
|---|---|---|
| P0: observation/reference binding | An old snapshot ref must not resolve to a different element after another snapshot. Establish a failing regression in original code, then reject stale refs with zero wrong-element clicks in isolated real Chromium. New refs must still dispatch real clicks. Cover same-node refresh, replacement, reload plus new snapshot, cross-page use, clones/concurrent allocation and exhaustion. | Fix only the demonstrated reference reuse defect; preserve the current MCP selector/ref grammar and backend trait. |
| P1: observation efficiency and coverage | Compare existing AX observation and the unmodified pinned upstream DOM reader on local controlled fixtures. Report actual target coverage and alternating observation latency, including negative cases such as shadow DOM and frames. | Adopt a replacement only if required coverage and semantics are preserved and measured benefit is repeatable. A local read microbenchmark does not establish end-to-end agent benefit. |
| P2: constrained model selection | The earlier offline probes establish response validation and expose absent confidence abstention and incomplete outcome coverage. Actual model value additionally requires a fixed model, representative tasks, full outcome checks and complete costs. | Retain an explicit evaluation design; do not substitute mocks for real model quality, install an unvalidated provider, or infer value from the upstream runtime comparison. |

## Implementation choice for P0

The initial research proposed explicit observation-generation binding. The
compatible implementation candidate is backend-lifetime unique numeric refs:
keep `@e<digits>`, share a checked counter across backend clones, and retain
only the most recently published ref map for each page. A prior ref then
becomes unknown instead of being reinterpreted. Counter exhaustion must
error without wraparound.

This is an assistant-selected route within the accepted goal, not a new user
requirement. No new MCP argument or provider is required. The full serialized
snapshot hash includes refs, so identical DOM captures will have different
hashes. It remains an output-artifact hash, not a normalized DOM digest.

The fix does not make observation plus action atomic, cancel clicks already
resolved before a later snapshot, prove freshness of arbitrary page state,
or eliminate geometry/focus/occlusion races. Concurrent snapshots retain the
last published map; this is not a claim about invocation order or newest DOM.

## Execution and custody

- Use test-first RED/GREEN evidence, followed by package tests, targeted
  formatting, Clippy where appropriate, and the normal repository pre-commit.
- Use a unique headless Chrome profile and only local/data fixtures; never
  attach to the existing user profile. Record and stop only this task's
  browser process, retain logs, and independently check process cleanup.
- Build on real disk. Keep small CLI fixtures on a unique owned ext4 path if
  the repository gate selects live CLI comparisons; do not reuse another
  session's fixed-output validation directory.
- Keep existing dirty worktrees, shared caches and installed runtime intact.
- Commit reviewed results with `[skip ci]`; preserve source and evidence on
  explicit review/backup branch refs without CI. Mainline publication and
  runtime deployment are distinct from this validation delivery.

Status at plan creation: validation pending. Results and any HOLD/NOT_RUN
decisions will be recorded below after the corresponding checks.
