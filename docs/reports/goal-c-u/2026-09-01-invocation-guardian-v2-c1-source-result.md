# Invocation Guardian v2 C1 source-canary result

Date: 2026-09-01

Status: **C1 SOURCE PASS; C2-C4 and production remain HOLD**

## Decision

The repository now contains a default-off, single-effect source canary. A real
MCP stdio child accepts a self-contained signed exact lease only from top-level
`tools/call.params._meta`, consumes it through an asynchronous fake witness,
and hands a fresh-only permit to a fixed marker sink. Concurrent replay produces
at most one successful dispatch and one marker.

This closes the source-level C1 gate only. The witness is an in-process map, the
guard is not an independently isolated guardian process, and the provider key
is test configuration. Nothing here proves protected monotonicity, UID/IPC
isolation, task identity, global effect coverage, or production authority.

## Implemented

- A default-off `invocation-guardian-v2-canary` feature and dedicated
  `invocation-guardian-canary-mcp` binary. Ordinary builds register no canary.
- An async fake witness with closed decisions, atomic fresh-vs-replay handling,
  signed receipts, and pre-commit / post-commit-response-loss fault injection.
- A private, non-`Clone` fresh permit. `AlreadyCommitted`, conflict,
  indeterminate, timeout, and hold cannot create the invocation handoff.
- An invocation-local MCP handoff bound to the finalized canonical tool name;
  it can be installed once, consumed once, and is recreated for every call.
- Recalculation and verification of tool, JCS arguments, fixed target, finalized
  registry digest, principal, namespace, time window, and server-owned stdio
  connection commitment before witness consumption.
- A fixed marker sink with no caller-selected arguments. It validates an
  absolute canonical owner-only `0700` root and uses directory-relative
  `O_NOFOLLOW | O_EXCL`, `0600` files, and file/directory sync.
- A real child-process stdio E2E covering missing authorization, nested `_meta`
  spoofing, two concurrent valid calls using one token, and the resulting
  exactly-one-success / exactly-one-marker postcondition.

## Verification

The C1 feature checks and focused tests used
`CARGO_TARGET_DIR=/var/tmp/agent-bridge-c1-target` where shown.

```text
cargo check -p ab-bridge --features invocation-guardian-v2-canary --no-default-features
PASS

cargo test -p ab-bridge --lib invocation_guardian_canary \
  --features invocation-guardian-v2-canary --no-default-features
4 passed / 0 failed

cargo test -p ab-mcp --lib guard_handoff_is_canonical_one_shot_and_invocation_local \
  --features invocation-guardian-v2-canary --no-default-features
1 passed / 0 failed

cargo test -p ab-bridge --test invocation_guardian_v2_canary_stdio \
  --features invocation-guardian-v2-canary --no-default-features
1 passed / 0 failed

cargo test -p ab-bridge --lib invocation_lease_scope --no-default-features
4 passed / 0 failed

cargo test -p ab-bridge --lib invocation_guardian_protocol_v2 --no-default-features
4 passed / 0 failed

cargo check -p ab-bridge --no-default-features
PASS

git diff --check
PASS
```

The new/modified Rust files pass targeted `rustfmt`. Repository-wide
`cargo fmt --all -- --check` remains red because the inherited snapshot has
large pre-existing formatting drift outside this change; no formatting sweep
was performed. Existing compile warnings also remain and are not attributed to
the C1 modules.

## Explicit HOLD boundary

- no independent guardian UID, process, peer-credential check, or authenticated
  IPC channel;
- no protected witness outside the Bridge host rollback domain;
- no anti-rollback, provider failover, stale-replica, recovery, or key-rotation
  deployment evidence;
- no installed profile, service restart, publication, or production canary;
- no task-principal custody and no coverage beyond the one fixed marker ingress;
- v1 remains volatile-lab and non-authoritative; ordinary production
  `AB_INVOCATION_LEASE_MODE=enforce` remains Invalid/HOLD.

The next gate is C2 deployment isolation. It requires operator-owned deployment
choices and real UID/IPC probes; local source tests cannot self-approve it.
