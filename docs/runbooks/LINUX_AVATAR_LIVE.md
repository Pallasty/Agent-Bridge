# Linux Avatar Live

`agent-bridge avatar linux-live` is the bounded EAP-1A owner-local embodiment
loop. It refreshes one stable `agent_presence` row from the current pet sidecar
while a native transparent Wayland surface polls the same sidecar for visual
state changes.

It is deliberately a foreground dogfood command. It does not install a systemd
unit, write the pet sidecar, emit audio or notifications, control desktop input,
execute queued actions, or enable `embodiment-runtime-p4`.

## Preflight

The binary must be built with `linux-native-avatar`, and the current session
must provide the verified wlroots/Wayland transparent backend:

```bash
agent-bridge avatar backend-probe
agent-bridge avatar linux-live \
  --project agent-bridge \
  --pet-id xiao-shu-v2 \
  --dry-run --json
```

Dry-run reads the sidecar and desktop environment only. It does not open
`state.db`, write presence, or create a Wayland surface.

## Owner-local trial

```bash
agent-bridge avatar linux-live \
  --project agent-bridge \
  --pet-id xiao-shu-v2 \
  --role embodiment-dogfood \
  --duration-ms 1800000 \
  --heartbeat-interval-secs 15 \
  --state-poll-ms 500
```

While it runs, inspect the projected row from another terminal:

```bash
agent-bridge avatar surface \
  --project agent-bridge \
  --role embodiment-dogfood \
  --max-idle-secs 30
```

Expected behavior:

- the session id stays `com.agentbridge.avatar-live.agent-bridge` unless
  explicitly overridden;
- sidecar `mode`, activity, focus, risk, evidence and next action flow into the
  presence projection on each heartbeat;
- the transparent surface follows sidecar mode changes without mutating the
  official Codex pet package;
- after the foreground process exits, the row is not refreshed and naturally
  becomes stale under the caller's presence TTL.

The completion receipt proves that the Wayland loop returned and reports
heartbeat counts. It does not claim that compositor pixels or the physical
display were independently observed.

## Promotion boundary

Do not install an automatic user service yet. First collect at least ten real
task-state transitions and confirm that state changes are timely, useful, and
free of duplicate rows. Audio remains a separate EAP-1B gate, with Qwen3-TTS as
the production backend and explicit cooldown/enable controls.
