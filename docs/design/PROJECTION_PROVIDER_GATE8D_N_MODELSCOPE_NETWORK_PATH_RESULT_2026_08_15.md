# Projection Provider Gate 8D-N: ModelScope Network Path Result

Date: 2026-08-15

## Result

The current Windscribe path can reach the ModelScope ABot Studio origin and
its first-load assets. There is no evidence that application split tunneling
is required for the next bounded provider attempt.

## Observations

Windscribe was connected to `London - 1984` over `Stealth:443` with its
firewall enabled. DNS resolved the Studio host through
`all.ms.show.c.yundunwaf5.com` to `39.96.127.68`, and the route used `utun6`.

Read-only probes produced:

- origin HEAD: HTTP 200, TLS complete, 7.71 seconds total;
- origin GET: HTTP 200, 161735 bytes, 3.76 seconds total;
- repeated request bound to `utun6`: HTTP 200, 3.60 seconds total;
- manifest, JavaScript, CSS, and iframe-resizer assets: HTTP 200;
- certificate valid from 2025-12-15 through 2027-01-16;
- request bound to physical `en0`: connection timeout after 8 seconds while
  the Windscribe firewall remained enabled.

The probes did not submit a prompt, start ABot inference, acquire a body lease,
write a Gate 8A task, or change VPN/WARP settings.

## Split-Tunnel Decision

Do not add the current ModelScope path to Windscribe application isolation.
Agent-Bridge launches or controls Google Chrome, so excluding the Chrome app
would bypass the VPN for unrelated browser activity. Excluding
`agent-bridge.real` would not route Chrome's network process.

If a future controlled comparison proves that only the VPN path fails, first
provision a dedicated Chromium-family executable and profile for Agent-Bridge,
then isolate only that dedicated browser. Do not isolate the shared daily
Chrome application.

## Next Gate

Gate 8D-E is one explicitly authorized `modelscope_abot_run_once` attempt:
preview a fresh request, acquire a process-local body-write lease, execute once,
release the lease, and retain the durable result. No automatic retry is
admitted. Network readiness does not prove provider compute availability.
