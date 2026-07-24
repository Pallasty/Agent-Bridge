# Free Recall Strategy R31 — C2C-B Curate Phase Instrumentation

Date: 2026-07-24

Status: **SOURCE-ONLY / NO LIVE RUN AUTHORIZED**

Parent: R30 Attempt-1 was incomplete after MCP initialization and before the
`session_curate` response. The ordinary, non-observation fixture completed, so
the next question is bounded to the explicitly attached observation sidecar or
the immediately adjacent core-save calls.

## Objective

Add a default-off, lab-only checkpoint channel that can identify the last
completed segment of one future disposable run. It must not diagnose by
capturing raw process output.

## Exact design

Only the `episode-observation-c2c-keychain-macos-live-lab` feature compiles
the checkpoint writer. If the explicitly passed
`AGENT_BRIDGE_C2C_LIVE_LAB_PHASE_PATH` names the driver's temporary file, the
child may append only one of these fixed labels:

```text
curate_entered
candidates_ready
observation_begin_enter / observation_begin_done
core_save_enter / core_save_done
observation_item_enter / observation_item_done
observation_finish_enter / observation_finish_done
curate_response_ready
```

The parent creates and owns that temporary file, reads it only after the child
has been killed/reaped and the stdout reader joined, then returns at most the
last whitelist label. Unknown file contents are ignored. The response contains
no request text, MCP stdout/stderr, memory key, Keychain service/account/epoch,
or database path.

## Non-goals and constraints

- No live Keychain, MCP, database, deployment, or merge is authorized by R31.
- No normal/default build gains an environment-driven output path.
- The channel does not change core curate or observation behavior: failures to
  open/write/read it are ignored.
- R31 does not reinterpret R30 and does not permit a retry under R30.

## Acceptance gate

1. The existing R27 static/mutation gate still passes.
2. Default features remain buildable without the lab module.
3. The lab feature builds and driver tests prove unknown checkpoint text cannot
   escape the whitelist.
4. Review confirms the only cross-process payload is a temporary file path and
   fixed labels.

## Next authority boundary

A separate R32 preregistration is required before one future disposable live
probe may use this instrumentation. Its outcome must be recorded once and is
not automatically retryable.
