# G1 Authenticated Freeze-Authority Adapter Isolated-Lab Result

Date: 2026-07-18

Verdict: **PASS — SYNTHETIC IMPLEMENTATION GATE ONLY / NO AUTHORITY**

## Scope completed

- Added an immutable public isolated-lab contract bound to the exact
  preregistration and hardened G1.3 artifacts.
- Added a default-disabled Darwin synthetic module implementing restricted
  exact RFC 8785 JCS, RFC 8032 Ed25519 KAT signing/verification, retained
  no-follow custody, a repository-external trust/claim ledger double, signed
  checkpoint and durable high-water checks, absorbing success/denial CAS, and
  a process/key-bound one-use capability.
- Added a standalone adversarial checker and shell entry point.
- Documented production gaps and kept G1.4, candidate access, execution,
  retrieval mutation, live writes, and runtime promotion closed.

## Artifact identities

| Artifact | SHA-256 |
| --- | --- |
| isolated-lab contract | `f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14` |
| implementation | `50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94` |
| Python checker | `e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e` |
| shell entry point | `6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895` |

## Verification evidence

- TDD RED: the new shell checker failed with `ModuleNotFoundError` before the
  implementation module existed.
- TDD GREEN: `259` adversarial assertions/mutations passed with
  `PASS_SYNTHETIC_ISOLATED_LAB_NO_AUTHORITY`.
- RFC 8785 UTF-16 ordering and restricted-domain rejection cases passed.
- RFC 8032 Ed25519 test vector 1, tamper, and noncanonical-point cases passed.
- Partial quorum, key injection, invalid signature, revoked key, durable denial,
  and post-denial replay cases passed.
- Hardlink, symlink, file mode, directory mode, final-name swap, in-place byte
  mutation, and remote mount cases passed.
- Expiry, same-boot monotonic/checkpoint regression, fresh-boot monotonic reset,
  stale new-boot checkpoint, boot mismatch, sequence gap, post-success replay,
  and stale database snapshot cases passed.
- An invalid-time absorbing denial was shown to consume sequence/nonce/digest
  without advancing trusted-time high-water; a later valid claim passed.
- Closed-schema deletion, key substitution behind a restored trigger, claim
  event rewrite, and time high-water rewrite cases passed.
- A constructor failure injected before context-manager entry left no private
  fixture or ledger directory behind.
- Python `py_compile`, Black check, Pyflakes, and `bash -n` passed after the
  implementation stabilized.

The first direct `black --check` command failed because no `black` executable
was on `PATH`; `python3 -m black` was available and became the verified entry
point. This was a tool-discovery issue, not a source failure, and changed no
project dependency.

An independent ledger-focused review found that the first implementation
compared monotonic nanoseconds across different boot epochs. That made the
contract's fresh-checkpoint reboot path unreachable whenever the new monotonic
clock restarted below the old value. The finding was reproduced, fixed by
scoping monotonic order to the active boot epoch, and covered by the new
fresh-boot regression case. The same audit prompted the unverified-denial
high-water case above. A post-commit pathname drift remains deliberate
fail-closed quarantine: the external anchor is not advanced across an
untrusted name-to-inode transition, and automatic continuation is forbidden.

## Safety boundary

The checker generates only public nonsecret synthetic files in exact temporary
owner-only directories and removes those generated directories afterward. No
real key, credential, private corpus, candidate material, runtime, MCP surface,
network provider, or live store is used. No manual safety-audit transition was
triggered. Real provisioning, key governance, scope/filesystem widening, and
first production enablement remain separately audited transitions.
