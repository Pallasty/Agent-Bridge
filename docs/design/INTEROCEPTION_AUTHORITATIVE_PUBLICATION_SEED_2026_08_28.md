# AB interoception: authoritative publication and independent seed

Date: 2026-08-28

Status: **R9-M5 agent-seed extension `SOURCE_READY` locally at
`c38497ec8ff033f483d99d8dbb98dfacb67b8dfd`; the preceding R9 chain is
published at authoritative GitLab `master`; CI deliberately skipped; live
independent seed acquisition is the next bounded operation; not provisioned,
deployed, or live-admitted; production `HOLD`**.

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
  manifest, known-hosts digest, current authoritative master, source
  repository, absent seed target, and either a private GitLab key or an exact
  agent-socket/public-key/fingerprint identity into a confirmation.
- `publish` is the only remote writer. It requires the exact
  `PUBLISH:<candidate>:<plan_digest>` value, permits only a fast-forward of the
  existing GitLab master, pushes the exact object to `refs/heads/master`, uses
  GitLab push option `ci.skip`, then independently rereads master.
- `acquire-seed` writes only an absent seed through a private sibling stage.
  It clones from GitLab with `--no-local --no-hardlinks`, checks out the exact
  authoritative candidate, freezes the expected `gitlab` tracking config,
  normalizes private modes, durably syncs the tree, and activates it with
  Linux atomic no-replace rename plus parent-directory sync.
- `verify` independently requires GitLab master, seed HEAD, tracking ref, and
  candidate equality plus clean status, exact authority config, private inode
  custody, and no gitlinks.

All authentication and known-hosts paths must be shell-safe canonical physical
paths below non-replaceable ancestry. Files are owned mode `0600`; file-key
mode requires an OpenSSH private-key envelope. Agent mode requires an owned
mode-`0600` Unix socket, an exact mode-`0600` public key, and its SHA-256
fingerprint to be present in that agent. Git receives `IdentitiesOnly=yes`
with the public key as the identity selector, so unrelated agent identities
are not offered. Known-hosts may identify only GitLab. File bytes, public-key
identity, socket device/inode/mode/owner, and agent membership are revalidated
before every Git operation. Git otherwise runs with a bounded clean
environment, disabled global/system configuration, disabled
hooks/replacements, strict host verification, and no prompt.

No force push, branch creation, tag, merge, CI pipeline, service action,
deployment-root creation, credential generation, or production mutation is
provided. An absent authoritative master blocks rather than allowing this tool
to initialize it. Existing seed/stage paths are never reused or overwritten.

## Verification and current truth

The isolated harness uses a real bare Git remote with push-option support and
proves plan read-only behavior, exact confirmation, fast-forward publication,
explicit CI skip, independent clone, seed verification, dirty input, malformed
manifest, unsafe private-input modes, existing seed, post-clone tamper, exact
agent identity binding, and racing-target non-replacement: `6/6 PASS` with
warnings as errors. The updated R9-M2 provisioning harness is `10/10 PASS`,
proving the birth receipt still binds the publication/seed orchestrator.

Correction measured 2026-08-29 and implemented in R9-M5: the Codex process had
not inherited `SSH_AUTH_SOCK`, but the current desktop session exposes an owned
mode-`0600` gcr agent socket at `/run/user/1000/gcr/.ssh`. Its agent-only
ED25519 identity authenticates GitLab as `@pallasting`, and a clean-environment
`ls-remote` reads authoritative master. The orchestrator now consumes that
already-loaded identity without exporting private key material. A new key is not required for
current operator publication or independent seed acquisition. This
current-boot identity does not automatically satisfy the durable fixed-file
key contract used by R9-M2 and unattended publication.
