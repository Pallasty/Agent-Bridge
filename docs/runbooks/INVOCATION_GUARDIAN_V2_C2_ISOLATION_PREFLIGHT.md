# Invocation Guardian v2 C2 isolation preflight

Date: 2026-09-01

Status: **probe tooling ready; C2 gate HOLD**

## Purpose and boundary

This runbook executes the Linux UID/IPC attack matrix required before an
Invocation Guardian v2 deployment can be considered isolated. The helper is
protocol-free and non-authoritative. It proves only the tested operating-system
substrate; it is not a guardian, a witness, or production deployment evidence.

The harness is default-off and intentionally refuses to create users, groups,
persistent systemd units, or production directories. A root operator must name
three existing, distinct non-root identities:

- guardian: owns private state and the Unix socket parent;
- bridge: belongs to one dedicated socket group and is the only admitted peer;
- agent/tool: does not belong to that group and must not connect.

The dedicated socket group must differ from all three primary groups.

## Build and non-mutating host preflight

```bash
CARGO_TARGET_DIR=/var/tmp/agent-bridge-c2-target \
  cargo build -p ab-bridge \
  --bin invocation-guardian-isolation-probe \
  --features invocation-guardian-v2-isolation-probe \
  --no-default-features

scripts/invocation-guardian-v2-c2-isolation-preflight.sh --preflight-only
```

`--preflight-only` never elevates privileges or changes the host. `HOLD` is the
correct result when root or three existing non-root identities are unavailable.

## Full ephemeral substrate probe

After an operator has selected the identities and reviewed their memberships:

```bash
sudo scripts/invocation-guardian-v2-c2-isolation-preflight.sh \
  --binary /var/tmp/agent-bridge-c2-target/debug/invocation-guardian-isolation-probe \
  --guardian-user AB_GUARDIAN_USER \
  --bridge-user AB_BRIDGE_USER \
  --agent-user AB_AGENT_USER \
  --socket-group AB_GUARDIAN_SOCKET_GROUP
```

The script copies the exact helper bytes to a root-owned `0755` file beneath a
new `/run/ab-invocation-guardian-c2.*` root. It starts the helper as a transient
systemd service with `NoNewPrivileges`, empty capability sets, strict system
protection, private devices/tmp, kernel/control-group protection, AF_UNIX-only
networking, and explicit writable state/socket paths. Bridge and Agent probes
also run as transient systemd services, preventing ambient listener-FD custody.

No password or credential is accepted through command-line arguments. The
operator enters sudo authorization through the normal terminal mechanism.

## Required machine-observed results

The final JSON is emitted only when all conditions hold:

- guardian, Bridge, and Agent are distinct non-root kernel UIDs;
- socket group is dedicated; Bridge has it and Agent does not;
- Bridge connects and authenticates the guardian through reciprocal
  `SO_PEERCRED` checks;
- Agent cannot complete the authenticated ping;
- neither Bridge nor Agent can open private state for read or write;
- neither can unlink or rename guardian state;
- neither can unlink, rename, or replace guardian-owned socket nodes;
- neither can `PTRACE_ATTACH` the guardian;
- neither inherits the guardian listener FD.

The success label is `ISOLATION_SUBSTRATE_PASS`, while `c2_gate` deliberately
remains `HOLD_actual_v2_guardian_not_deployed`.

## Promotion rule

C2 may be marked PASS only after the actual v2 guardian composition—not this
helper—runs under the reviewed persistent service configuration and the same
attack matrix is repeated against its real state, socket, process, Bridge
caller, and Agent/tool identities. Unit-file property inspection, a same-UID
test, a container-only simulation, or a successful helper run alone is not
sufficient.

C3 protected-witness work remains independent and HOLD.
