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

Sparse voice remains disabled unless the owner explicitly enables its separate
read-only observer. For the authenticated Mac LAN route:

```bash
export AB_FACE_VOICE_ENABLED=1
export AB_FACE_VOICE_BACKEND=qwen3-lan
# Also export the four AB_QWEN3_LAN_* values from MACOS_QWEN3_TTS_PILOT.md.
./scripts/dock/face-native-launch.sh
```

Before detaching anything, the launcher runs `avatar voice-observe --dry-run`
and fails closed unless the plan reports `ready=true`. The observer starts no
renderer, writes neither presence nor pet state, begins silently, and shares
the renderer's process group only for reliable lifecycle teardown. Override its
bounded segment, poll, cooldown, and budget with `AB_FACE_VOICE_SEGMENT_MS`,
`AB_FACE_VOICE_POLL_MS`, `AB_FACE_VOICE_COOLDOWN_SECS`, and
`AB_FACE_VOICE_MAX_UTTERANCES`.

Check the lifecycle without parsing process listings:

```bash
./scripts/dock/face-native-launch.sh --status
./scripts/dock/face-native-launch.sh --status --json
```

The JSON status distinguishes `running`, `supervisor_only`, and `stopped`, and
reports the renderer PID, stable optional `voice_supervisor_pid`, transient
`voice_observer_pid`, current invocation's `voice_configured` flag, and
renderer-state endpoint reachability. A voice worker restart changes only the
transient PID while retaining its voice supervisor.

Stop the session-owned Avatar explicitly:

```bash
./scripts/dock/face-native-launch.sh --stop
```

Stop validates the supervisor and also sweeps only exact native renderer
processes, so an orphaned Wayland child cannot leave a visible face behind.

This is intentionally a foreground-session workflow with a detached child,
not a launchd/systemd installation. The launcher uses a user-private runtime
lock and validates process identity before suppressing duplicate starts.
