# Agent-Bridge R0 Project Truth and Roadmap Reset Result

Date: 2026-08-10

Initial implementation base: `005695e42ddc3f54a316df5849ba1806fc45def3`.

Forum preregistration: design thread 373, post 6083.

## Verdict

`R0_TOOLING_VALIDATED_CURRENT_PROJECT_HOLD_RECONCILIATION_REQUIRED`

R0 tooling and the active product roadmap are validated. The observed project itself is not aligned and remains `HOLD_SOURCE_RUNTIME_REMOTE_DIVERGENCE`; no merge, install, restart, deployment, cleanup, or WIP mutation was performed.

## Observed project truth

- Shared source checkout: `44a4b2d043debf6fe3583d18cab54f3c5b6ba5aa`, branch `master`, dirty with 106 porcelain status entries.
- Direct GitLab/GitHub master consensus: `b3d76b5b34479a81e4bb4d9627252e6f50cab83d` at the final evidence capture.
- Installed binary artifact: version `0.14.0`, source prefix `005695e42ddc`.
- Connected MCP process observed separately through `capabilities` earlier in this R0 session: source prefix `bc2f6a386927`; this is external session evidence, not a claim produced by the snapshot command.
- Worktree inventory: 40 total, 35 clean, 5 dirty, 0 unobserved at final capture.
- Mismatches: source worktree dirty, source HEAD differs from remote, and installed binary differs from remote.
- Recommended action: preserve dirty WIP and reconcile from a clean remote-tracking worktree before build or deployment.

Counts are a point-in-time observation and may change as other isolated worktrees are created, completed, or modified.

## Product reset

- Core product: memory usefulness, session continuity, sync, install/update truth, and daemon/MCP reliability.
- On-demand capabilities: subagents, worktrees, terminal, browser, and voice only for real tasks.
- Experimental lanes: capped and default-frozen until a current user problem plus measurable trial justifies reopening.
- Active sequence: R0 truth, R1 real-task memory usefulness, R2 lower coordination ceremony, R3 continuity dogfood.
- Further private custody, crash-artifact exclusion, ExplicitTrajectory gates, world-model runtime admission, and new synthetic protocol families are not active product goals.

## Evidence

- Snapshot source SHA-256: `66d1c97d475aaaf728f3c6c427918a9538fd7727dd57a0b6df0751b49c20b546`.
- Final observed packet SHA-256: `00a6273fca0c656a2c27ed08f6766d793f5a41e95f40d56e80d6036c1f3d5410`; 3918 bytes.
- Expected live snapshot exit status: 4 (structured HOLD).
- Focused suite: 13/13 passed.
- `git diff --check`: passed.
- Independent protocol/product review: ACCEPT; 0 critical, 0 major, 0 minor.
- Independent implementation/test review: ACCEPT; 0 critical, 0 major, 0 minor.

## Review-driven corrections

The draft overclaimed that executing an external binary was side-effect-free, counted unobservable worktrees as clean, accepted incomplete or short binary provenance, and could recommend a live smoke when source status was missing. The final tool reports only writes it requested, marks the external binary subprocess side effects unproven, requires version plus a minimum 12-character source SHA, keeps dirty/clean/unobserved worktrees separate, rejects credential-bearing remote forms, disables optional Git locks, and gives an observation-completion action whenever any required source, remote, binary, or worktree fact is missing.

## Nonclaims

Remote probing does not fetch or mutate local refs. Inventory does not clean or remove worktrees. Installed-binary identity does not prove the currently connected MCP process. `READY_ALIGNED`, if reached later, will still require a fresh-process health and MCP smoke before deployment acceptance.
