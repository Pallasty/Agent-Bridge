# AB interoception: authoritative publication and independent seed

Date: 2026-08-28

Status: **R9-M3 `SOURCE_READY` locally at
`2107da2f0560f98c2820700f11c64093afd37783`; CI deliberately skipped; not
published, seeded, provisioned, deployed, or live-admitted; production `HOLD`**.

## Purpose

R9-M2 can safely create the trusted deployment root once an authoritative
candidate and an eligible standalone seed exist. R9-M3 closes the preceding
handoff without treating a development worktree as authority:

```text
clean local candidate
  -> authenticated GitLab fast-forward publication (ci.skip)
  -> independent authenticated clone
  -> private standalone seed verification
  -> R9-M2 plan/provision/verify
```

The implementation is `scripts/publish-and-acquire-trusted-seed.py` with four
commands:

- `plan` performs no local or remote write. It binds the exact candidate,
  manifest, private GitLab key and known-hosts digests, current authoritative
  master, source repository, and absent seed target into a confirmation.
- `publish` is the only remote writer. It requires the exact
  `PUBLISH:<candidate>:<plan_digest>` value, permits only a fast-forward of the
  existing GitLab master, pushes the exact object to `refs/heads/master`, uses
  GitLab push option `ci.skip`, then independently rereads master.
- `acquire-seed` writes only an absent seed through a private sibling stage.
  It clones from GitLab with `--no-local --no-hardlinks`, checks out the exact
  authoritative candidate, freezes the expected `gitlab` tracking config,
  normalizes private modes, and atomically renames the stage.
- `verify` independently requires GitLab master, seed HEAD, tracking ref, and
  candidate equality plus clean status, exact authority config, private inode
  custody, and no gitlinks.

The key and known-hosts paths must be shell-safe canonical physical paths
below non-replaceable ancestry. Both files are owned mode `0600`; the key must
have the OpenSSH private-key envelope and known-hosts may identify only
GitLab. Git runs with a bounded clean environment, disabled global/system
configuration, disabled hooks/replacements, strict host verification, no
agent, and no prompt.

No force push, branch creation, tag, merge, CI pipeline, service action,
deployment-root creation, credential generation, or production mutation is
provided. An absent authoritative master blocks rather than allowing this tool
to initialize it. Existing seed/stage paths are never reused or overwritten.

## Verification and current truth

The isolated harness uses a real bare Git remote with push-option support and
proves plan read-only behavior, exact confirmation, fast-forward publication,
explicit CI skip, independent clone, seed verification, dirty input, malformed
manifest, unsafe private-input modes, existing seed, and post-clone tamper:
`4/4 PASS` with warnings as errors. The updated R9-M2 provisioning harness is
`10/10 PASS`, proving the birth receipt now binds the R9-M3 orchestrator.

The node's actual GitLab probe still returns `Permission denied (publickey)`.
Therefore no real plan can become ready and no publication or seed acquisition
occurred. The next live step requires the release owner to provision a reviewed
mode-`0600` GitLab key and known-hosts file outside unsafe HOME ancestry, then
run plan, inspect the candidate and remote identities, and explicitly supply
the emitted confirmation.
