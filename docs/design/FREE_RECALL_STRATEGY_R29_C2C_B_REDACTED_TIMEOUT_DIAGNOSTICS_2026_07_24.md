# Free Recall Strategy R29 — C2C-B Redacted Timeout Diagnostics

Date: 2026-07-24

Status: **SOURCE-ONLY PREREGISTRATION / NO LIVE AUTHORITY**

Parent: R28 Attempt-1 timed out after all no-Keychain gates passed.

## Goal

R29 makes a future live decision observable without retaining or emitting
MCP stdout/stderr, memory keys, Keychain identifiers, epochs, or secret data.
It changes only the default-off fixture driver's in-memory timeout handling.

## Exact source surface

| Path | Change |
| --- | --- |
| `crates/bridge/src/bin/episode_observation_c2c_live_lab.rs` | Always join the bounded stdout reader after child exit/kill and classify only the highest completed JSON-RPC phase. |
| `scripts/eval/free_recall_strategy_r27_c2c_live_lab_source.py` | Assert the redacted phase classifier, join-on-timeout, and no raw output forwarding. |
| `docs/design/FREE_RECALL_STRATEGY_R29_C2C_B_REDACTED_TIMEOUT_DIAGNOSTICS_2026_07_24.md` | This preregistration and source result. |

No R25 runtime, Keychain custody module, schema, registry, build defaults,
deployment, merge, or live invocation is in scope.

## Redacted result contract

The driver may report exactly one of these public classes on timeout:

```text
before_initialize_response
after_initialize_before_curate_response
after_curate_response_before_exit
```

It must not print the response body, tool result, child stderr, memory key,
account name, epoch, item reference, or any error string from the child.

## Acceptance

1. all existing source and fake tests pass;
2. unit tests prove each phase class from synthetic JSON-RPC lines;
3. a timeout kills/waits the child and joins its reader before returning;
4. the static gate fails if raw stdout/stderr forwarding is introduced.

R29 grants no new live run. A later R30 preregistration must decide whether a
fresh disposable live experiment is warranted from the redacted phase result.
