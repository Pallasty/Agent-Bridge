# Agent Runtime Workspace Sandbox P1

Status: opt-in implementation and evidence gate (2026-07-17)

## Decision

Agent-Bridge adopts grok-build's `nono` pattern at the per-child executor
boundary, not at the daemon boundary. A hidden `agent-bridge` launcher applies
an irreversible Landlock (Linux) or Seatbelt (macOS) policy and then replaces
itself with the requested agent process. This covers one-shot, interactive PTY,
and protocol-native ACP runtimes through the same launch contract.

No runtime human approval is introduced. Recoverable work remains autonomous.
The human/security review point is promotion or policy broadening, because a
credential disclosure caused by a sandbox defect cannot be undone by rolling
back the binary.

## P1 policy

- Gate: `AGENT_BRIDGE_AGENT_SANDBOX=workspace`; default `off`.
- Precedence: daemon policy is a floor. A per-spawn env value can opt in but
  cannot turn an ambient workspace policy off.
- Read: host filesystem, except explicit credential denies.
- Write: canonical workspace, temp paths, selected runtime state, and existing
  build/package caches.
- Network: open. P1 is a filesystem boundary, not an exfiltration-proof
  network boundary.
- Environment: remove Bridge API tokens, SSH agent/askpass handles, cloud
  credentials, and package-registry tokens. Preserve model-provider keys.
- Launcher integrity: sandboxed spawns cannot override `HOME`, `TMPDIR`,
  `PATH`, or dynamic-loader variables. The daemon's inherited values define
  policy and binary lookup; this prevents pre-sandbox path broadening or code
  injection.
- Remote/cloud: fail closed. Wrapping a local SSH or cloud client is not
  equivalent to sandboxing the executor.
- Unsupported platform/missing enforcement: fail closed when explicitly
  enabled.

## Platform construction

On macOS, `nono = 0.53.0` emits the Seatbelt profile. Read denies are added
after broad read grants. Credential write denies include concrete write
actions as well as `file-write*`, preserving the grok-build finding that a
later broad workspace write grant can otherwise win. `/private` aliases are
covered for `/tmp`, `/var`, and `/etc` paths. Because `nono` also blocks
Keychain Mach services, native TLS verification can otherwise fail with
`UnknownIssuer`. Sandboxed children therefore default `SSL_CERT_FILE` to the
root-owned `/etc/ssl/cert.pem` when neither the daemon nor the spawn supplied a
value. This preserves provider networking without exposing the login keychain.

On Linux, Landlock cannot subtract a child path from a read grant on `/`.
The outer launcher therefore re-execs under bubblewrap, overlays sensitive
directories with mode-000 tmpfs mounts and sensitive files with anonymous
mode-000 read-only files populated from an inherited EOF descriptor, then the
inner launcher applies Landlock. The backing inode has no host path that the
target could chmod through another writable directory. Missing bubblewrap or a
failed mount aborts the child.

`nono` is pinned exactly. A version bump requires rerunning the macOS denial
contract and Linux bubblewrap/Landlock contract before merge.

## Credential deny set

P1 hides common SSH, AWS/Azure/GCP, Kubernetes, Docker, GPG, GitHub/GitLab,
git, npm, PyPI, Cargo, netrc, macOS Keychain, and Agent-Bridge credentials.
Path-bearing credential env vars are retained only long enough for both Linux
launcher stages to construct the deny set, then removed before the target
starts.

Runtime-specific model authentication remains intentionally available. This is
the convenience/security boundary: an executor must be able to call its model,
but should not inherit unrelated control-plane credentials.

## Audit and promotion gate

Routine sandboxed execution does not require approval. A trust-boundary audit
is required before any of these changes:

1. Change the default from `off` to `workspace`.
2. Broaden writable paths, credential visibility, or network access.
3. Change the bubblewrap mount plan or remove fail-closed behavior.
4. Upgrade `nono` or alter Seatbelt deny ordering/actions.
5. Claim support for remote/cloud execution.
6. Accept a materially different `nono` transitive dependency or license set.

The audit consumes automated evidence rather than per-action prompts:

| Evidence | Required claim |
|---|---|
| macOS Seatbelt e2e | workspace write succeeds; outside write and fake credential read/write fail; child exec works |
| Linux bwrap + Landlock e2e | same contract, including a deny nested under a writable cache; missing `bwrap` fails closed |
| Runtime regression | all local one-shot, PTY, and ACP launch paths retain lifecycle/output behavior |
| Secret-env probe | unrelated tokens absent; model-provider keys present |
| Remote/cloud probe | explicit workspace policy is rejected before session launch |

## P1 evidence accepted on the feature branch

The following evidence was collected on 2026-07-17 before mainline promotion:

- macOS: ten sandbox tests pass, including a process-isolated Seatbelt e2e that
  writes the workspace and a synthetic cache, denies outside writes, denies an
  exact credential nested under that writable cache, and executes a child.
  A built-binary hidden-launcher smoke also confirmed control-token removal and
  model-key preservation.
- Linux aio2: Ubuntu kernel `7.0.0-27-generic`, bubblewrap `0.11.1`, and the
  branch binary through `fd11f3b7` passed the full
  `bwrap -> inner nono/Landlock -> target -> child` contract. Existing file and
  directory secrets returned `EACCES`/read-only errors, workspace writes
  persisted, a sibling host write was denied, host secret contents were
  unchanged, and launcher-only env was absent.
- Linux fail-closed: setting `AGENT_BRIDGE_BWRAP_BIN` to a missing executable
  returned a non-zero launcher error before the target ran. Nine Linux sandbox
  unit tests pass, including canonical-target handling for symlink aliases.
- Cross-runtime regression: the local Agent and Bridge suites, all-target Bridge
  check, touched-file rustfmt/diff checks, and strict Agent clippy gate pass;
  only repository-pre-existing warnings and explicitly documented ignored real
  provider probes remain.
- Supply chain: all newly resolved packages expose license metadata through
  `cargo metadata`; `nono` is Apache-2.0. `cargo audit`/`cargo deny` were not
  installed, so an advisory scan remains part of the default-on promotion audit.

## Known P1 limits

- Open network means a readable, non-denied secret can still be exfiltrated.
- Linux bind-over protects the resolved launch-time deny set; future policy
  additions need corresponding mount-plan tests.
- Linux P1 bind-over skips deny paths that do not exist at launch, because
  mounting onto a missing destination under a host-root bind creates a host
  mountpoint. Such a path has no existing secret contents; if its parent is
  writable, the target may create new data there. Path inspection errors still
  fail closed. Symlink aliases are not mount destinations; their canonical
  targets are mounted instead, so alias access resolves into the same denial.
- macOS uses the process-specific `$TMPDIR`; it does not grant the whole
  `/private/var/folders` tree writable.
- Common cache directories are writable for build usability and may contain
  tool-specific state not yet classified.
- P1 does not sandbox `shell_exec`, terminal injection, the daemon, or an IDE.
- P1 does not claim xAI inference acceptance when the local `grok` executable
  or account authentication is unavailable.
- `nono 0.53.0` is Apache-2.0, but its current default-feature-disabled crate
  still brings a sizable trust/signing dependency graph. Keep the exact pin and
  track an upstream sandbox-only split rather than silently widening supply-chain
  surface during upgrades.

Promotion should follow evidence, not elapsed soak time. A failed test or
rollback must be recorded as a lesson with the violated assumption, observed
failure, containment, and regression guard.
