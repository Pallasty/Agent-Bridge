# Mobile projection MCP tool

Date: 2026-08-11

## Outcome

Agent-Bridge now exposes `mobile_projection_start` to `codex-essential` and
other policy surfaces that already include the Android mobile bridge. A Codex
session can open one bounded projection consent page with a single tool call;
the device holder still decides whether the phone connects.

## Enforced behavior

- required caller inputs: reachable private/link-local bind IP, title, body;
- optional selected ADB serial and 1–600 second TTL;
- OS-random 32-byte token retained in process memory and omitted from results;
- OS-selected port avoids a fixed-port collision;
- previous companion Activity/process is stopped before the new consent page;
- no companion service start, sensor request, click injection, or authority;
- projection thread ends at TTL or immediately when its MCP process exits;
- payload authentication remains plaintext-on-trusted-LAN, so secrets are out
  of scope.

The tool result reports `awaiting_device_consent`, session, endpoint, expiry,
device serial, false authority flags, and that the token was not exposed.

## Live MCP validation

Validation used the real `agent-bridge mcp` stdio server with
`AGENT_BRIDGE_TOOLSET=codex-essential`, an OPPO PKW110 on Android 16/API 36,
and host/device LAN addresses `192.168.1.16`/`192.168.1.7`.

The first call revealed that Android could reuse an already-visible expired
Activity. The tool returned success but the new consent data was not rendered.
The implementation was corrected to launch with `am start -S`, which replaces
any prior projection before presenting new consent.

On the corrected call:

1. MCP returned `awaiting_device_consent`, a random port, a 300-second expiry,
   `token_exposed=false`, and every authority flag false.
2. The phone displayed the new source/session/expiry consent page.
3. The device holder explicitly pressed **Allow and connect**.
4. The phone rendered `Agent-Bridge tool projection` and the exact test body.
5. Activity Manager reported no `CompanionService` throughout.
6. The device holder pressed **Disconnect**; the page showed
   `Disconnected by you` with a disabled button.
7. The MCP validation process was terminated, immediately dropping the
   listener rather than waiting for TTL.

## Gates

- `cargo check -p ab-bridge --lib`: PASS;
- `cargo test -p ab-bridge codex_essential_exposes_mobile_bridge_tools --lib`:
  1 passed, 0 failed;
- `cargo test -p ab-bridge 'mobile_' --lib`: 17 passed, 0 failed;
- `git diff --check`: PASS.

This slice improves daily Agent-Bridge utility. It does not broaden sensing,
remote control, publication, or external-validation goals.

## Media context extension (2026-08-13)

The same authenticated, ephemeral frame can now carry an optional
`agent_bridge.media_context.v0` object. It is read-only display data: player,
active playlist object path/name, playback status, track identity, position,
duration, metadata availability, and observation time. The frame rejects other
schemas and bounded text violations. `MediaContext::changed_from` provides a
small value-based change detector so a producer can skip duplicate mobile
updates. Clearing or replacing the context is explicit in
`mobile_projection_update`; no control callback or authority field is added.

The lifecycle tools are intentionally exposed only by the named
`AGENT_BRIDGE_TOOLSET=codex-mobile-projection` profile. `codex-essential` and
`codex-lean` retain status/wait or other read-only mobile tools but must not
silently gain projection start/update/stop. After changing the toolset, the MCP
process must be reconnected before its schema changes are visible.
