# Linux Avatar entrypoint

The native transparent renderer is a bounded probe. For a reusable desktop
Avatar, use the session-owned supervisor:

```bash
./scripts/dock/face-native-launch.sh
```

It keeps one native renderer alive in a detached process group, respawns the
renderer if it exits, and does not install a system service or emit audio.
The default placement is the bottom-right of the compositor's default output.
Its compact desktop projection is `90x130` with a 39% sprite scale—one quarter
of the original `360x520` dimensions while retaining the complete figure.
Override these together with `AB_FACE_WIDTH`, `AB_FACE_HEIGHT`, and
`AB_FACE_SPRITE_SCALE_PERCENT` when a different projection size is desired.
The default native surface is an XDG toplevel with app id
`agent-bridge-avatar`; the launcher makes it floating, sticky, and borderless
under Sway. Hold Super and drag with the left mouse button to reposition it.
Set `AB_FACE_DRAGGABLE=0` to retain the anchored layer-shell surface instead.
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

The launcher defaults sparse voice to `AB_FACE_VOICE_GAIN_DB=8`. The adapter
applies gain only to an ephemeral playback copy, then peak-limits it with
automatic output normalization disabled. It never changes the sink, music, or
system master volume; the adapter hard-clamps the setting to `0..8 dB`.
The first owner-heard live acceptance of this baseline is recorded in
`docs/reports/avatar/2026-08-22-sparse-voice-live-acceptance.md`. Its slightly
fast pace is a deferred profile preference; do not silently change the frozen
gain or instruction while operating this baseline.

Each actual adapter decision is appended to the user-private runtime log
`$XDG_RUNTIME_DIR/ab-face-voice-receipts.jsonl` (override with
`AB_FACE_VOICE_RECEIPT_LOG`). Records contain bounded status, decision,
evidence identifiers, engine identity and playback gain fields only—no audio,
spoken text, LAN address, socket path, or credentials. The log rotates to one
`.1` file at 1 MiB.

Summarize the current and rotated logs without emitting audio or exposing
spoken text:

```bash
./scripts/dock/face-voice-observation.sh
```

The observation remains `collecting` until it contains at least six naturally
occurring successful speech decisions spanning 24 hours. These are sampling
thresholds, not proof of physical audibility or future delivery. Override them
only for an explicitly labelled experiment with
`AB_FACE_OBSERVATION_MIN_SPOKEN` and
`AB_FACE_OBSERVATION_MIN_WINDOW_SECS`.

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

## Read-only focus-follow planning

Preview where Xiao Shu could move when explicitly asked to attend to the
currently focused Sway window:

```bash
agent-bridge avatar focus-follow-plan --json
```

This command reads the Sway tree and returns a bounded docking path plus a
`turn_*`, `walk_*`, `arrive_settle` choreography. It never dispatches that
path, moves the Avatar, follows the pointer, changes keyboard focus, or emits
input. The feature is default-off and fail-closed. Its action registry also
lists `wave`, but the generated v3 action sheet is a concept asset only: it
failed transparent-alpha validation and is not bound to the renderer.

This is intentionally a foreground-session workflow with a detached child,
not a launchd/systemd installation. The launcher uses a user-private runtime
lock and validates process identity before suppressing duplicate starts.
