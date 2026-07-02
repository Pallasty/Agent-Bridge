# Nexus API Contract Review Branch Handoff

Date: 2026-07-02

## Scope

This report records the safe follow-up after cleaning
`/Data/CascadeProjects/nexus-civilization`.

The goal was to make the valuable Nexus API contract work reviewable without
pushing the local Nexus `main` history, because that history contains large
tracked Android build artifacts.

## Current Nexus State

- Nexus worktree: clean.
- Local branch: `main`.
- Upstream: `github/main`.
- Local `main`: `6a5e901`.
- `github/main`: `f775b20`.
- Local `main` is ahead of `github/main` by 79 commits.

Do not push Nexus `main` directly. The history range `github/main..HEAD`
contains blobs over 100 MB:

- `client/godot/android/build.bak.20260415-044343/libs/debug/godot-lib.template_debug.aar`
- `client/godot/android/build.bak.20260415-044343/libs/release/godot-lib.template_release.aar`

## Safe Branch Created

Created a clean review branch from `github/main` and cherry-picked only the
API contract documentation commit:

- Local branch: `reconcile/nexus-api-contract-20260702`
- Remote branch: `github/reconcile/nexus-api-contract-20260702`
- Commit: `68c13ba docs: add comprehensive API contract for multi-client architecture`
- Diff: adds `docs/API_CONTRACT.md` only

GitHub PR URL:

```text
https://github.com/pallasting/nexus-civilization/pull/new/reconcile/nexus-api-contract-20260702
```

## PR Packet

Title:

```text
docs: add multi-client API contract
```

Body:

```markdown
## Summary

Adds `docs/API_CONTRACT.md`, a comprehensive API contract for the Nexus
multi-client architecture.

## Scope

- Documentation only
- New file: `docs/API_CONTRACT.md`
- Based directly on `github/main`
- Does not include local `main`'s 79-commit history
- Does not include tracked Android/Godot build artifacts

## Safety Note

Local Nexus `main` is ahead of `github/main`, but that full history contains
>100MB Android build artifacts and should not be pushed directly. This branch
cherry-picks only the API contract doc so it can be reviewed safely.

## Verification

- `git diff --stat github/main..reconcile/nexus-api-contract-20260702`
- Result: one new documentation file, 599 insertions
```

## Request-Pull Summary

```text
The following changes since commit f775b20c0bd2c1683baa16ce3163e488efaf270b:

  feat(engine): Phase A 续 — agent_boot.py 6-stage + npc_persona AgentIdentity 集成 (2026-05-07 02:48:26 -0700)

are available in the Git repository at:

  git@github.com:pallasting/nexus-civilization.git reconcile/nexus-api-contract-20260702

for you to fetch changes up to 68c13ba01d141e3e0acbac08395b0628374a5a4b:

  docs: add comprehensive API contract for multi-client architecture (2026-07-02 05:30:07 -0700)

----------------------------------------------------------------
pallasting (1):
      docs: add comprehensive API contract for multi-client architecture

 docs/API_CONTRACT.md | 599 +++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 599 insertions(+)
 create mode 100644 docs/API_CONTRACT.md
```

## Boundary

No PR was opened by automation because the environment has no `gh`, no `hub`,
and no GitHub token. Only the review branch was pushed.
