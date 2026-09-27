# Repository publication and backup roles

Decision: 2026-09-27, owner direction. This file records source distribution
roles; it does not grant permission to publish an unreviewed change or enable a
runtime feature.

| Role | Repository | Mainline | Purpose |
|---|---|---|---|
| Public release | `https://github.com/Pallasty/Agent-Bridge` | `main` | Canonical links, source installs, reviewed releases and tags |
| Backup | `https://gitlab.com/pallasting/agent-bridge` | `master` | Independent Git forge and source copy |
| Backup | `https://github.com/pallasting/Agent-Bridge` | `master` | Existing account's source copy |

The remotes on the current node are `pallasty` (SSH host alias
`github-secondary`), `origin` (GitLab) and `github` (old GitHub account).
Other nodes can use different remote names; verify URLs before pushing. The
release URL in public documentation is HTTPS and does not depend on the local
SSH alias. No bare `git push` should be treated as a release operation.

## Publish a source commit

1. Select an explicitly reviewed, committed source SHA from a clean worktree.
   Check its tree, build/test evidence as appropriate, current release `main`,
   and both backup heads. An old or dirty local `master` is not a source SHA.
2. Confirm the candidate descends from release `main` and that each backup
   `master` can fast-forward to the same candidate. Resolve divergence in a
   separate reviewed branch; never force-push a release or backup mainline.
3. Push the exact SHA to `Pallasty/Agent-Bridge` `main`, then read it back with
   `git ls-remote`. This is the publication point.
4. Push that same SHA to GitLab `master` using `-o ci.skip`, then to the old
   GitHub `master`. Include `[skip ci]` in sync commits while existing GitHub
   backup workflows still listen to `master`. Verify all three remote hashes.
5. A version tag is a separate release decision. Push the exact tag object to
   all three repositories and compare remote tag refs. Do not manufacture a
   version bump or tag merely to make mirror refs look equal.

Illustrative explicit ref commands (replace `<sha>` only after step 2):

```bash
git push pallasty <sha>:refs/heads/main
git ls-remote git@github-secondary:Pallasty/Agent-Bridge.git refs/heads/main
git push -o ci.skip git@gitlab.com:pallasting/agent-bridge.git <sha>:refs/heads/master
git push github <sha>:refs/heads/master
```

Use a direct GitLab URL for GitLab push options: GitHub does not accept its
`ci.skip` push option. Never use `--mirror` from a working clone or push all
local branches: this clone has historical experiments and local worktree refs.
Bring across selected review branches explicitly when needed. Backup mirrors
may lag while a release candidate is under review; record the exact heads
rather than implying parity.

## Account settings

On the release repository, protect `main` from force pushes and deletion, and
add a release review rule that fits the owner's workflow. Protect version
tags from deletion or replacement. Settings/API permissions are separate from
Git SSH access; verify those controls in GitHub before claiming they are active.

The old GitHub repository currently has workflows on pushes to `master`.
For a passive backup, disable its automatic Actions runs in that repository's
settings or retain `[skip ci]` on each synchronized commit. Check workflow
triggers again when they change. No repository setting is inferred from this
document alone.
