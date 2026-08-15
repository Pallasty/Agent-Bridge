# Projection Provider Gate 8B: ModelScope Recovery Guard

Date: 2026-08-15

## Goal

Gate 8B prevents repeated external attempts while ModelScope ABot-World is in
a recently observed provider failure window. It derives recovery readiness
from Gate 8A durable task records and does not add a health-check request,
background worker, automatic retry, or persistent provider session.

## Status Surface

`modelscope_abot_provider_status` is a read-only projection. It reports:

- the latest terminal task and last successful task time;
- provider failures observed after the last success;
- whether the bounded cooldown is active and its expiry;
- task scan counts and the fixed 256-record scan limit;
- local runtime opt-in, Browser capability, and backend presence;
- blockers that prevent a later explicitly authorized one-shot call.

The tool reads regular JSON task files only. It performs no network probe,
browser action, lease acquisition, retry, or runtime enablement. Prompt text,
receipts, and raw error strings are not returned by this aggregate surface.
Malformed or incomplete task history is reported as `task_history_invalid`;
the execution path fails closed instead of ignoring uncertain history.

## Cooldown Policy

Only `provider_timeout` and `provider_lifecycle` failures affect provider
cooldown. Browser, artifact, concurrency, and local validation failures do not
claim that the hosted provider is unhealthy.

A `running` record owned by an earlier MCP process is projected as
`interrupted_after_restart` and enters the first cooldown step. This treats an
uncertain browser/provider lifecycle conservatively without mutating or
resuming the old record.

Consecutive provider failures after the latest completed task use these
cooldowns: 5 minutes, 15 minutes, 30 minutes, then 60 minutes for the fourth
and later failures. A completed task resets the streak. Expiry makes a new
explicit call eligible; it does not start one.

`modelscope_abot_run_once` evaluates this state after completed-task replay
inspection and before opening a browser or writing a new running task. During
an active cooldown it returns `provider_cooldown` with the retry timestamp and
states that no external execution started. Completed idempotent replays remain
available during cooldown because they do not repeat external work.

## Authority Boundary

Gate 8B does not weaken Gate 8A controls. A later live call still requires the
named toolset, Browser capability, runtime environment opt-in, an active body
write lease, `owner_confirmed=true`, and a new request id after any failed or
interrupted task. There is no cooldown override in this gate.
