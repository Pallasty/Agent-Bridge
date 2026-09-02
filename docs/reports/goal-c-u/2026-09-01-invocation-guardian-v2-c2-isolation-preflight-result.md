# Invocation Guardian v2 C2 isolation-preflight result

Date: 2026-09-01

Status: **C2 PREFLIGHT TOOLING READY; host execution HOLD; C2-C4 and production HOLD**

## Outcome

The repository now has a default-off Linux isolation probe and a root-only,
ephemeral systemd harness for the C2 attack matrix. It can produce machine-read
JSON evidence from real distinct UIDs without creating users, groups,
persistent units, or production paths.

The current host cannot execute the full matrix in this session: effective UID
is 1000, passwordless sudo is unavailable, and NSS exposes only one ordinary
user. The non-mutating host preflight therefore correctly returned:

```json
{"schema":"agent_bridge.invocation_guardian_c2_host_preflight.v1","status":"HOLD","reason":"root_and_three_distinct_existing_nonroot_users_are_required","effective_uid":1000,"nonroot_user_count":1,"ptrace_scope":"1","systemd_state":"running","production_authority":false}
```

No deployment identity or host policy was changed.

## Implemented evidence surface

- `invocation-guardian-v2-isolation-probe` is gated by the default-off
  `invocation-guardian-v2-isolation-probe` Cargo feature.
- The server validates guardian/state/socket ownership and exact modes, admits
  only the configured Bridge kernel UID, and records its real PID and listener
  FD inode.
- Bridge and Agent attack modes measure reciprocal peer credentials, group
  membership, state read/write/unlink/rename, socket unlink/rename/replace,
  ptrace attach, and inherited listener-FD presence.
- The harness requires distinct existing non-root identities and a dedicated
  group, copies fixed helper bytes into a root-owned runtime path, and uses
  transient hardened systemd services for the server and both attackers.
- All mutable artifacts are bounded to a fresh validated
  `/run/ab-invocation-guardian-c2.*` directory and cleaned on exit.
- A helper substrate success remains explicitly non-authoritative and leaves
  the C2 gate on HOLD until repeated against the actual v2 guardian service.

## Verification

```text
cargo check -p ab-bridge --bin invocation-guardian-isolation-probe \
  --features invocation-guardian-v2-isolation-probe --no-default-features
PASS

cargo build -p ab-bridge --bin invocation-guardian-isolation-probe \
  --features invocation-guardian-v2-isolation-probe --no-default-features
PASS

cargo test -p ab-bridge --bin invocation-guardian-isolation-probe \
  --features invocation-guardian-v2-isolation-probe --no-default-features
3 passed / 0 failed

cargo check -p ab-bridge --no-default-features
PASS; isolation probe remains default-off

cargo test -p ab-bridge --test invocation_guardian_v2_canary_stdio \
  --features invocation-guardian-v2-canary --no-default-features
1 passed / 0 failed; C1 real-stdio regression preserved

bash -n scripts/invocation-guardian-v2-c2-isolation-preflight.sh
PASS

scripts/invocation-guardian-v2-c2-isolation-preflight.sh --preflight-only
HOLD as expected; evidence reproduced above

same-UID helper server negative execution
PASS: server rejected guardian_uid == expected_bridge_uid

full-probe invocation as non-root
PASS: refused with exit 77 before mutation

cargo clippy (focused binary, without promoting inherited warnings to errors)
PASS: no diagnostic attributed to invocation_guardian_isolation_probe.rs
```

`cargo clippy -- -D warnings` remains unsuitable as a change-local gate because
the inherited dependency graph contains many pre-existing warnings. No unrelated
clippy or formatting sweep was performed.

## Remaining gate

An operator must select or provision three real service identities and the
dedicated group, authorize the root run, review the transient result, then wire
the actual v2 guardian composition under equivalent persistent service-manager
controls and repeat the matrix. Until then C2 is not passed. C3 still requires
an external protected monotonic witness and anti-rollback evidence.
