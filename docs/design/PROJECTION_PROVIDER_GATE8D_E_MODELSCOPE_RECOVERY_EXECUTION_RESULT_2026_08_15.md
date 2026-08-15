# Projection Provider Gate 8D-E: ModelScope Recovery Execution Result

Date: 2026-08-15

## Verdict

`GATE8D_E_PROVIDER_TIMEOUT_CLEANLY_CLOSED`

The owner explicitly authorized one external ModelScope ABot request. The
request reached the Studio execution path but the stream did not report a
positive FPS before the deadline. No retry was attempted.

## Bound Request

- request id: `gate8d-e-recovery-trial-20260815-001`
- task id: `abot-task-20d1ed2960eac3665290eea6`
- observation window: 5000 ms
- prompt SHA-256:
  `5bc39105f3579962518c14a6c00fd0ff080349d994041eb9aed5a08bda335be4`
- request digest:
  `0b325f1ba68fa357d7354de9797d9768ebddb55b93c77e7d28c934bf5eb3a28c`

The prompt text is not persisted in the Gate 8A task record.

## Execution Evidence

The first invocation used a lease for a non-canonical body id and was rejected
before any external action. That unused lease was released. The authorized
request then used a process-local lease for the canonical `body-mac` body.

The durable task reports:

- status: `failed`;
- failure class: `provider_timeout`;
- positive FPS not observed before the deadline;
- Studio stop cleanup observed;
- browser close observed;
- persistent runtime not admitted;
- retry policy requires a new request id.

The canonical body lease was released immediately after the call and a
read-only status check confirmed no remaining lease.

## Recovery State

After this attempt, the provider projection reported six valid task records,
three consecutive provider failures, no prior success, and an active 30 minute
cooldown. The execution preflight is blocked by `provider_cooldown_active`.

Gate 8D-N previously proved that the Studio origin and first-load assets were
reachable through Windscribe. This result therefore does not justify adding
shared Google Chrome to application isolation or changing VPN/WARP settings.

## Boundary

The external authorization was consumed by this single attempt. Do not retry
automatically or reuse this request id. A future attempt requires cooldown
expiry, a new preview and request id, a fresh owner decision, and a new
process-local body lease.
