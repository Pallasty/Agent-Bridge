# Projection Provider Gate 8A: ModelScope Task Protocol

Gate 8A adds a durable scheduling envelope around the live Gate 7Z
`modelscope_abot_run_once` operation without admitting a background or
persistent executor.

## Contract

- Existing calls remain compatible when `request_id` is omitted.
- A call with `request_id` derives a stable `abot-task-<24 hex>` identifier and
  a SHA-256 request digest bound to provider, request id, prompt hash, and
  observation window, plus the optional embodiment intent id.
- Task records use `agent_bridge.modelscope_abot_task.v0` and are atomically
  written below `~/.cache/agent-bridge/modelscope-abot/tasks/`.
- The task directory is mode `0700`; records are staged as mode `0600`, synced,
  renamed, and followed by a directory sync before success is reported.
- Prompt text is not persisted in the task record; only its SHA-256 digest is
  stored.
- A completed retry with the same request id and request digest returns the
  stored receipt with `idempotent_replay=true` and
  `external_execution_repeated=false`.
- Reusing a request id with different inputs fails as `idempotency_conflict`.
- Failed tasks never auto-retry. A new request id is required.
- A `running` record owned by an earlier MCP process is projected as
  `interrupted_after_restart`; it is never resumed automatically.

## Status Surface

`modelscope_abot_task_status` reads a task by stable task id. It may omit the
nested receipt for compact polling. The projection is read-only and does not
change the durable record, acquire a lease, open a browser, or resume work.

## Failure Classes

Gate 8A records stable classes for provider timeout, provider lifecycle,
artifact I/O, concurrency busy, and browser backend failures. Input,
capability, lease, opt-in, and browser-availability gates still fail before
external execution; they do not create a misleading running task.

## Authority Boundary

The execution path still requires Browser capability, an active process-local
body write lease, `owner_confirmed=true`, and
`AB_MODELSCOPE_ABOT_RUNTIME_ENABLE=1`. Gate 8A adds replay and observability; it
does not authorize persistent runtime, automatic retry, queued background
execution, or restart recovery.
