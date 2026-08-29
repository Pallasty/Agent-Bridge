# AB interoception: GitLab deploy credential ceremony

Date: 2026-08-29

Status: **R9-M4 `SOURCE_READY` locally at
`573ae19b6f530d0cfb52be9b88acb8292a5390e4`; CI deliberately skipped; no
real key generated or enrolled, no publication/deployment occurred, and
production remains `HOLD`**.

## Missing organ

R9-M3's file-key mode can publish and independently acquire a seed only after
it receives a physical mode-`0600` GitLab private key and verified known-hosts.
Correction measured 2026-08-29: the node also has a usable current-boot
agent-only identity behind `/run/user/1000/gcr/.ssh`; it authenticates GitLab
as `@pallasting`. R9-M4 is optional for the current operator push, not a
prerequisite. It remains relevant only if the release owner chooses a
separately governed persistent deploy key for R9-M2/unattended publication.

R9-M4 provides a bounded local credential ceremony:

```text
read-only plan
  -> exact GENERATE:<plan_digest> confirmation
  -> fresh Ed25519 key + official GitLab known-hosts in private stage
  -> local not-enrolled receipt
  -> atomic no-replace activation
  -> independent local verify
  -> operator enrolls public key with write_repository access
  -> R9-M3 authenticated plan proves enrollment
```

The implementation is `scripts/prepare-gitlab-deploy-credential.py` with
`plan`, `generate`, and `verify`. It never calls a GitLab API, opens a network
connection, prints private material, edits SSH configuration, or claims that a
locally generated key has repository authority.

## Trust and custody

The manifest binds an absent target, exact project path, and bounded key
comment. Manifest, parent, target, stage, and every generated file must be
physical, owned, privately permissioned, and below non-replaceable ancestry.
Generation uses `/usr/bin/ssh-keygen` in a bounded environment and creates one
unencrypted Ed25519 deploy key for unattended publisher use. The target
contains only mode-`0600` files beneath a mode-`0700` directory:

- `gitlab_deploy_key` and matching `.pub`;
- `known_hosts` containing the three GitLab.com host keys;
- `enrollment.json`, which exposes only the public key/fingerprint and remains
  explicitly `not_enrolled` with required access `write_repository`;
- `receipt.json`, which binds all file digests, official host fingerprints,
  manifest/plan, project, and `local_key_not_enrolled` authority state.

The host-key anchors were checked on 2026-08-29 against the official
[GitLab.com settings documentation](https://docs.gitlab.com/user/gitlab_com/#ssh-host-keys-fingerprints):

- ED25519 `SHA256:eUXGGm1YGsMAS7vkcx6JOJdOGHPem5gQp4taiCfCLB8`;
- ECDSA `SHA256:HbW3g8zUjNSksFbqTiUWPWg2Bq1x8xdGUrliXFzSnUw`;
- RSA `SHA256:ROQFvPThGrW4RuWLoL9tq9I9zJ42fK4XywyRtbOz/EQ`.

`verify` recomputes those fingerprints using `ssh-keygen`, derives the public
key from the private key, compares it to the stored public key, and rehashes
the exact receipt file set. A deterministic pre-existing stage is preserved
and blocks. Activation uses Linux `renameat2(RENAME_NOREPLACE)` after file and
directory fsync, then fsyncs the parent. An appearing target cannot be
overwritten.

## Authority boundary and verification

Local generation is not enrollment. Only later authenticated GitLab
`ls-remote`/fast-forward publication path can prove that GitLab accepts the
key. If this optional route is selected, the operator must register the public key on
`pallasting/agent-bridge` with write repository access and retain an independent
GitLab-side audit record. CI is outside this lane and was explicitly skipped.

Adversarial local verification:

- R9-M4 credential ceremony: `4/4 PASS` with warnings as errors;
- R9-M3 publication/seed: `4/4 PASS`;
- R9-M2 provisioning: `10/10 PASS`;
- Python AST and whitespace gates: `PASS`.

The harness covers zero-write planning, wrong confirmation, duplicate/unknown
manifest state, unsafe modes/ancestry, existing target/stage preservation,
happy generation/verification, public/private mismatch, official host-key
tamper, receipt tamper, and file-mode drift. No CI or live key ceremony ran.
