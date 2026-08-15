# Projection Provider Gate 8C: ModelScope Attempt Preview

Date: 2026-08-15

## Goal

Gate 8C makes the identity and admission state of one proposed ModelScope ABot
call inspectable before an owner grants per-call authority or a caller acquires
the body-write lease. It does not retry the provider or infer recovery from a
local preflight.

## Read-Only Surface

`modelscope_abot_attempt_preview` accepts the same prompt, observation window,
request id, and optional embodiment intent id that define a Gate 8A task. It
uses the production digest derivation and returns:

- the stable task id, request digest, prompt digest, and observation window;
- whether an existing task is a replay, conflict, failure, interruption, or
  currently running request;
- the current Gate 8B recovery projection;
- typed blockers for a later explicitly authorized call.

The prompt is hashed in memory and is neither echoed nor persisted. The preview
does not accept `owner_confirmed` or `embodiment_lease_id`, acquire a lease,
write a task record, open a browser, probe the network, or execute the provider.

## Admission Semantics

- A new request is blocked by malformed provider history or an active cooldown.
- A completed digest-matched request remains a replay candidate even during a
  provider cooldown, matching the Gate 8A execution ordering.
- A digest conflict, prior failure, or prior-process interruption requires a
  new request id.
- Runtime opt-in, Browser capability, and browser backend presence remain
  visible blockers for both execution and replay calls because the live tool
  checks them before reading an existing task.

`ready_for_authorized_call=true` means only that local preconditions and request
identity are coherent. It is not evidence that ModelScope is healthy and it
does not grant execution authority.

## Authority Boundary

A later `modelscope_abot_run_once` call still requires a fresh explicit owner
decision, `owner_confirmed=true`, and an active process-local body-write lease.
Gate 8C admits no automatic retry, queued execution, persistent runtime, or
cooldown override.
