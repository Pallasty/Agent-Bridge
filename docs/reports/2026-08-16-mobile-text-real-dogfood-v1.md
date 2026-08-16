# Mobile text real-task dogfood V1 result

Date: 2026-08-16

## Verdict

`PASS_USEFUL`

The existing foreground mobile-text path removed one desktop surface switch
and one desktop text/copy action from a real Agent-Bridge device-readiness
handoff. Codex consumed the observation through the exact-session MCP status
surface and used it to confirm that the mobile acceptance workflow could
continue. No new protocol, APK, background service, deployment, or authority
surface was required.

The machine-readable decision is in
`2026-08-16-mobile-text-real-dogfood-v1-scorecard.json`. This report and the
scorecard intentionally omit the observation body.

## Evidence chain

- The workflow, baseline, success threshold, privacy rule, and separate
  authority gates were preregistered before the formal trial.
- The installed runtime was `9dc1c7276415` after the final MCP reconnect.
- The tested device was the separately authorized OPPO PKW110 on Android 16.
- The existing Companion `0.2.0` package remained installed and unchanged.
- The formal projection used explicit display confirmation and
  `auto_connect=false`; the Companion service was not started.
- The formal session accepted exactly one unique foreground submission.
- An exact-session `mobile_projection_status` call returned that observation
  with `attention_authority=false`, `memory_authority=false`, and
  `actuation_authority=false`.
- The fact was needed by the active device-readiness workflow and confirmed the
  next-step readiness decision. It did not authorize an ADB, APK, deployment,
  merge, or push action.
- `mobile_projection_stop` stopped the listener and force-stopped the Companion
  Activity; the prior foreground application was visible afterward.
- The startup toolset was restored from `codex-mobile-projection` to
  `codex-modelscope-abot`, and a fresh MCP process returned `projection session
  not found in this MCP process` for the formal session id.

## Scorecard

| Axis | Baseline | Trial | Result |
| --- | ---: | ---: | --- |
| Desktop surface switches | 1 | 0 | saved 1 |
| Desktop text/copy actions | 1 | 0 | saved 1 |
| Unique accepted observations | n/a | 1 | pass |
| Exact-session consumption | n/a | yes | pass |
| Affected a real decision | n/a | yes | pass |
| Background capture | n/a | no | pass |
| Implicit control | n/a | no | pass |
| APK mutation | n/a | no | pass |
| Runtime deployment | n/a | no | pass |
| Full text persisted in artifacts | n/a | no | pass |
| Fresh MCP can retrieve old session | n/a | no | pass |

## Honest limitations

- A first runtime attempt was stopped and excluded because its submission was a
  placeholder rather than a real task fact. Transport success from that attempt
  was not counted as use value.
- This is one bounded real workflow, not evidence that mobile text helps every
  Agent-Bridge task.
- The measured saving is interaction ceremony, not task duration or answer
  quality.
- The observation is session-local and visible to the consuming MCP process by
  design. The validated privacy boundary is no artifact/memory persistence plus
  process replacement after the trial, not end-to-end encrypted transport.

## Product decision

Retain the current mobile text input as an on-demand capability. Do not expand
it into background sensing, automatic attention, durable memory, device
control, or a broader voice product based on this single pass. The next useful
evidence should come from another naturally occurring workflow, not a synthetic
gate or a new protocol family.
