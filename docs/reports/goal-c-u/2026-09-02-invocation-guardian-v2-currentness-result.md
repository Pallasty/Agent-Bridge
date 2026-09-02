# Invocation Guardian v2 currentness reconciliation

Date: 2026-09-02

Status: **SOURCE LANE FROZEN; C0-C3 source evidence current; C2 host environment, C3 external provider, C4 and production HOLD**

## Decision

`5ccc2d9e955d1129385f0ebe66739a748a0e45a5` is the single current integration
candidate for the Guardian v2 work. It contains provider-lab head `468f235f`
and current `origin/master` head `a5ba8f8b`. The upstream delta touched five
macOS trusted-deployment files and did not conflict with Guardian paths.

This reconciliation adds no capability, policy layer, daemon, ledger, gate,
provider, credential, deployment identity, or production authority.

## Minimal regression evidence

All commands used debug builds, `-j1`, and `--no-default-features`.

| Boundary | Result |
| --- | --- |
| C0 lease scope | 4 passed, 0 failed |
| C0 signed provider receipt | 4 passed, 0 failed |
| C0 v2 protocol | 4 passed, 0 failed |
| C1 source canary | 4 passed, 0 failed |
| C1 real stdio E2E | 1 passed, 0 failed |
| C2 isolation probe binary | 3 passed, 0 failed |
| C3 protected-witness contract | 5 passed, 0 failed |
| C3 provider lab | 1 passed, 0 failed |
| default-off `ab-bridge` check | PASS |
| C2 shell syntax | PASS |
| `git diff --check` | PASS |

The read-only C2 host preflight reproduced `HOLD`: euid 1000, one available
non-root user, `ptrace_scope=1`, systemd running, and no production authority.

## Reversible C2 execution-path check

The owner has authorized autonomous execution of reversible work, so permission
to run a transient probe is no longer a blocker. The available disposable paths
were checked without changing repository or production state:

- passwordless elevation is unavailable;
- Docker, Podman, LXC, Incus and `systemd-nspawn` are absent;
- rootless user-namespace creation fails with `Operation not permitted`, despite
  configured subordinate UID/GID ranges;
- the user systemd manager cannot switch to another UID (`216/GROUP`), while the
  system manager correctly requires unavailable elevation; and
- the host still exposes only one ordinary non-root identity.

Therefore C2 remains `HOLD` for a technical environment prerequisite, not for
owner authorization. No substitute harness or synthetic PASS was added.

## Drift and overengineering audit

The security objective has not drifted: the implementation still targets one
default-off, fixed marker ingress and makes no global authority claim. The work
pattern, however, would drift if local source artifacts continued to be added
after all remaining gates became external-evidence gates.

The stop-drift fields are:

| Field | Current evidence |
| --- | --- |
| recent real problem | The motivating external incident is real; no analogous AB incident has been observed. |
| 30-day occurrences | No positive AB occurrence evidence is available. |
| owner cost per occurrence | Unmeasured because no AB occurrence has been recorded. |
| smallest owner-visible closure | Default-off C0-C3 source/lab invariants and explicit fail-closed boundaries already exist. |
| next increment | Run C2 or C3 against real external prerequisites; do not add source substitutes. |
| cost of doing nothing | The candidate remains dormant and production behavior stays unchanged. |

Verdict: further local implementation would increase proof machinery without
closing an observable AB gap. The Guardian source lane is therefore frozen.
Defect repair and regression checks remain admissible; new framework work does
not.

## Stop boundary

The source lane stops here. No further framework work is justified without one
of the already-defined external inputs:

1. C2 execution: an environment with distinct guardian, Bridge and Agent service
   identities and a root-capable transient-systemd execution context; or
2. C3 execution: an independently operated anti-rollback provider, endpoint,
   trust pins, credentials and recovery-test window.

Until one input exists, the smallest correct next action is HOLD. Either input
reopens only its matching evidence run, not general source expansion. C4 review,
installation, service restart, marker enablement and global enforcement are not
admissible next steps.

## Pre-PR currentness refresh

Before publication, the candidate was refreshed from upstream `a5ba8f8b` to
`c45ffd53`. The upstream delta changes only five macOS trusted-deployment shell
scripts and does not overlap Guardian paths. Merge `429aa213` was conflict-free.

Post-refresh checks:

- C3 provider lab: 1 passed, 0 failed;
- default-off `ab-bridge` check: PASS;
- `git diff --check`: PASS;
- accepted provider-lab commit `468f235f` remains included;
- frozen experimental commits `ca6110f7`, `f043320c`, `5816f710` and
  `090a849d` remain excluded.
