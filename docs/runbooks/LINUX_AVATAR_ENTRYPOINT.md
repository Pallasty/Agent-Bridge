# Linux Avatar entrypoint

The native transparent renderer is a bounded probe. For a reusable desktop
Avatar, use the session-owned supervisor:

```bash
./scripts/dock/face-native-launch.sh
```

It keeps one native renderer alive in a detached process group, respawns the
renderer if it exits, and does not install a system service or emit audio.
The default placement is the bottom-right of the compositor's default output.
The supervisor also refreshes a dedicated `native-face` presence session every
15 seconds, so the renderer-state source remains fresh instead of displaying a
stale session row. Override the interval with `AB_FACE_HEARTBEAT_SECS`.

Check the lifecycle without parsing process listings:

```bash
./scripts/dock/face-native-launch.sh --status
./scripts/dock/face-native-launch.sh --status --json
```

The JSON status distinguishes `running`, `supervisor_only`, and `stopped`, and
reports whether the renderer-state endpoint is reachable. A renderer restart
changes `renderer_pid` while retaining the same supervisor.

Stop the session-owned Avatar explicitly:

```bash
./scripts/dock/face-native-launch.sh --stop
```

Stop validates the supervisor and also sweeps only exact native renderer
processes, so an orphaned Wayland child cannot leave a visible face behind.

This is intentionally a foreground-session workflow with a detached child,
not a launchd/systemd installation. The launcher uses a user-private runtime
lock and validates process identity before suppressing duplicate starts.
