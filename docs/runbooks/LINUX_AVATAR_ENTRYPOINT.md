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

Preview where Xiao Shu could move when AB decides to express attention near the
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

Execute one reversible embodied-expression move:

```bash
agent-bridge avatar focus-follow-action \
  --execute --reason "AB chose to express attention near the focused task" --json
```

After a completed traversal, the command atomically records the acknowledged
target in `$XDG_RUNTIME_DIR/ab-focus-follow-ack.json`. Subsequent
`focus-follow-recommend` and `focus-follow-prompt` calls use that receipt when
`--last-target-node-id` is omitted, so the same focused window is not offered
again. An explicit `--last-target-node-id` overrides the receipt. Cancelled or
failed traversals never update it.

Acknowledgement v2 is accepted only when it is bound to the current compositor
session and the current exact Avatar node. A v1 receipt, a receipt from a prior
Sway session, or a receipt for a different Avatar node is ignored rather than
suppressing the wrong target.

Without `--execute`, this command is a dry-run. `--execute` records AB's
decision to express through its Avatar, and a non-empty auditable `--reason`
is required. `--confirm` remains accepted only as legacy owner-confirmation
provenance; it is not an authorization gate. The command resolves one exact
Avatar Sway `con_id`, moves only that node, and revalidates both the Avatar
identity and focused target before every
step, and never moves the pointer or keyboard focus. The default bounds are 48
pixels per step and 900 pixels total. `Ctrl-C` cancels the foreground action;
`--cancel-file PATH` also cancels before the next step whenever PATH exists.

## Bounded autonomous Focus-follow observer candidate

Increment 2 adds a deliberately non-persistent candidate around the same
one-shot action. Inspect its exact plan without starting a polling loop or
moving Xiao Shu:

```bash
agent-bridge avatar focus-follow-observe --json
```

Start one owner-local foreground observation session:

```bash
agent-bridge avatar focus-follow-observe --execute --json
```

The observer is default-off: omitting `--execute` returns the preflight
immediately. `--execute` starts only this invocation; it does not enable a
service, autostart, or a later session. The frozen defaults are 30 minutes
maximum duration, 1,000 ms polling, 2,000 ms stable-focus dwell, 300 seconds
post-action cooldown, 30 seconds initial exponential failure backoff capped at
900 seconds, 96..900 px eligible travel, and at most three real attempts.
Completed, cancelled, and failed actions all consume that attempt budget.
Caller options may lower the duration or attempt budget, but normalization can
never raise them above 30 minutes or three attempts.

Startup focus is a no-move baseline. A later stable target is suppressed when
it is acknowledged or already attempted, fullscreen, missing a structured
exact app identity, carries the exact `ab-sensitive` Sway mark on itself or an
ancestor, is an exact denylist match, paused, outside the travel bounds, in
cooldown/backoff, over budget, or unable to acquire the internal observer or
Focus-follow action lock. Below/above-bound suppressions are counted as
`below_min_travel` and `above_max_travel`.

At dispatch, the action freezes the exact target node, structured identity,
target rectangle, workspace rectangle, and workspace. Those gates are checked
again after taking the action lock, before every movement step, and at arrival.
Moving or resizing the focused window, moving it to another workspace, or
Super-dragging Xiao Shu away from the expected path cancels the old traversal;
a later stable observation may then form a new plan.

The built-in case-sensitive exact authentication/password-manager identities
are:

- Wayland app ids: `com.1password.1password`, `com.bitwarden.desktop`,
  `org.keepassxc.KeePassXC`, and `org.gnome.seahorse.Application`;
- XWayland classes: `1Password`, `Bitwarden`, and `KeePassXC`.

The observer never classifies window titles or substrings. Add an owner-local
exact identity to both structured identity sets without exposing it in the
receipt by repeating `--deny-app-id ID`.

The default pause signal is:

```text
$XDG_RUNTIME_DIR/ab-focus-follow-observer.pause
```

Create that file to suppress new movement. If it appears during an action, the
same path is passed as the action cancel file. Remove it to allow later eligible
focus changes within the still-running session. Use `--pause-file PATH` only
when an explicit owner-private runtime path is required; the live observer
fails closed without a usable private runtime directory.

Both observer and action locks live directly in the same owner-private
`XDG_RUNTIME_DIR`; changing `AGENT_BRIDGE_STATE_DIR`, `XDG_STATE_HOME`, or
`HOME` cannot create a second movement authority. The absolute observer
deadline is shared by tree reads, movement commands, and animation sleeps, so
no new movement command is issued after the bounded session expires.

There is no observer `--confirm` flag and no free-form per-move reason. The
observer never shows a prompt or bubble, emits audio, follows or moves the
pointer, changes keyboard focus, injects input, or operates the focused
application. A failed or cancelled target is not retried in the same run, and
failure backoff prevents poll-speed action loops.

The bounded final receipt is printed as a privacy-minimal JSON projection. The
runtime file is written first with `status=running` before movement is possible,
then atomically replaced with the terminal aggregate. It lives at:

```text
$XDG_RUNTIME_DIR/ab-focus-follow-observer-receipt.json
```

It contains only terminal status, aggregate counters, structured suppression
reasons, frozen bounds, and the zero-input effect/privacy contract. It contains
no window title, app id, raw Sway tree, path, prompt content, or free-form
reason. This ephemeral receipt is not an observer-run journal. Every real move
still writes the existing durable outcome v2 `started`/`final` pair described
below; that pair, not the observer aggregate, is action truth.

The aggregate distinguishes `tree_read_failure_count` from
`prestart_runtime_failure_count`. A proven pre-action lock/path/runtime failure
uses the closed `prestart_runtime_failed` suppression and does not consume an
attempt or masquerade as a sensor failure.

This observer remains an implementation candidate until the pending matrix in
`docs/reports/avatar/2026-08-24-focus-follow-bounded-observer.md` is completed
against a merged, deployed binary. Stop it with `Ctrl-C`; stopping the process
is the complete rollback because no background service is installed.

Every real execution appends a `started` record and a final outcome to
`$AGENT_BRIDGE_STATE_DIR/avatar-focus-follow/outcomes.jsonl`, when that common
state root is configured; otherwise it uses the same private subtree below
`$XDG_STATE_HOME/agent-bridge` and finally `~/.local/state/agent-bridge`.
Completed actions are positive outcomes; cancelled and failed actions are
durable negative-learning candidates. Outcome v2 gives both phases the same
random `attempt_id`; a started record with no matching final record exposes an
interrupted/internal-failure attempt even when rotation or concurrency separates
the two lines. Historical v1 rows remain evidence but are explicitly
unpairable.

Only the dedicated `avatar-focus-follow` directory is changed to owner-only
`0700`; the common state root is never chmodded. The log and lock file are
regular, single-link, non-symlink files restricted to `0600`, and rotation is
checked only before a new started phase at 8 MiB. If the initial private started
receipt cannot be persisted, execution fails before movement and instructs the
caller to select a permission-capable `AGENT_BRIDGE_STATE_DIR`. A storage fault
after movement can still prevent the terminal receipt; the durable started row
and its `attempt_id` make that failure observable on the next audit. The journal
stores no window title or free-form reason text.
Only actions whose final target, Avatar identity, and arrival position are
re-observed successfully update the acknowledged-focus receipt.

During an autonomous expression the native renderer reads the user-runtime file
`$XDG_RUNTIME_DIR/ab-face-motion-override.json`. The action publishes only
known RGBA v3 asset identifiers and removes the override on completion,
cancellation, or handled failure. Dedicated transparent turn, walk, and wave
atlases are runtime-bound; completion-nod is used for arrival settle.

The 2026-08-24 live traversal passed functional acceptance: all turn, walk,
arrival, wave, and idle transitions were visible, and the final docking point
was accepted. Fine-grained easing and stride tuning remain a deferred visual
polish item; they are not a correctness blocker.

The current owner-local AB is governed by reversible-expression autonomy:
Avatar position, motion, short bubbles, and already-policy-bounded sparse voice
do not require per-action user permission. A configurable permission layer may
be added if this surface is productized later. This does not grant authority to
move the pointer, inject input, operate applications, modify user data, expose
credentials, or perform irreversible/external actions.

This is intentionally a foreground-session workflow with a detached child,
not a launchd/systemd installation. The launcher uses a user-private runtime
lock and validates process identity before suppressing duplicate starts.
