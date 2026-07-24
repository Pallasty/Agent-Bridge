# Free Recall Strategy R32 — C2C-B Curate Checkpoint Probe

Date: 2026-07-24

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

Parent: R30 established that the fixture reaches MCP initialization but not a
`session_curate` response. R31 added a default-off redacted checkpoint channel
to distinguish the last completed curate segment without collecting raw output.

## Fixed envelope

Use R31 commit `3ee8cc20` or a descendant that changes no live-lab source.
After all preconditions pass, invoke exactly once:

```text
target/debug/episode-observation-c2c-live-lab \
  --agent-bridge "$PWD/target/debug/agent-bridge" \
  --execute-r26-live r26-c2c-live-authorized
```

The driver creates a fresh temporary SQLite database and checkpoint file, and
the existing custody creates then deletes only fresh random disposable
Keychain items. It does not enumerate or read an existing item.

## Preconditions

1. R27 static/mutation gate passes.
2. Default feature-disabled check passes.
3. The final R31 live-lab feature build and eight driver tests pass.
4. The isolated non-observation MCP fixture still saves one core memory.

## Result contract

Only one result is recorded:

- finalized receipt: record the finalized receipt shape;
- timeout: record only the existing redacted MCP phase and the optional final
  whitelisted checkpoint;
- any other incomplete result: record the bounded public error.

The child must be reaped before diagnostics are read. Cleanup/postcheck must
complete. R32 is not retried under this identifier.

## Non-goals

No deployment, merge, production configuration, broad Keychain access, or
additional retry is part of R32.
