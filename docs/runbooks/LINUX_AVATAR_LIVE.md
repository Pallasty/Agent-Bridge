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

## EAP-1B sparse Qwen voice

Voice feedback remains off unless the foreground invocation includes
`--voice-feedback`. EAP-1B accepts only an existing owner-local Qwen3-TTS worker
socket; it does not download weights, start a worker, fall back to another
engine, or keep the model resident after the operator stops it.

Deploy the binary and `scripts/audio_embody.py` together with the existing
version-matched deployment workflow. The live plan checks the
`agent_bridge.linux_live_qwen_voice.v1` adapter marker and fails closed when a
new binary is paired with an older deployed adapter.

Validate the worker without playing audio:

```bash
python3 scripts/validate_tts_worker_contract.py \
  --socket "$AB_QWEN3_TTS_WORKER_SOCKET" \
  --expected-engine qwen3-pytorch \
  --require-capability zh
```

Then inspect the complete live plan. This still emits no audio:

```bash
agent-bridge avatar linux-live \
  --project agent-bridge \
  --pet-id xiao-shu-v2 \
  --voice-feedback \
  --qwen-worker "$AB_QWEN3_TTS_WORKER_SOCKET" \
  --voice-cooldown-secs 300 \
  --voice-max-utterances 3 \
  --dry-run --json
```

Only after the plan reports `voice_feedback.ready=true`, run the same command
without `--dry-run`. The initial sidecar state is silent. A line is considered
only when the mode changes to `failed`, `verified`, `waiting_for_user`, or
`handoff`; `verified` additionally requires a real evidence id in the sidecar.
Lines are fixed Chinese templates, not arbitrary model text. The default global
cooldown is five minutes and one foreground session can successfully speak at
most three times.

`failed`, `waiting_for_user`, and `handoff` use fast playback and are honestly
reported as unverified at the output bus. `verified` uses the existing
PipeWire-monitor falsifier and cannot claim output-bus delivery unless the
captured envelope passes. Neither route proves headphone/speaker audibility;
continuous microphone listening remains out of scope.

## EAP-1C measurable trial receipt

Every non-dry live run now includes an `observation` object in its final JSON
receipt. Use `--json` and retain that stdout as the trial artifact. Observation
is read-only and bounded to 32 transition samples; it records sidecar polling,
read failures, observed mode transitions, the largest observed polling gap and
this process's peak resident memory. When voice is enabled, the voice receipt
also reports average and maximum adapter invocation time.

For a useful promotion sample, run at least ten real task transitions and review:

- `observation.sidecar.read_failures` is zero;
- `observation.sidecar.max_observed_poll_gap_ms` remains close to the configured
  polling interval under normal load;
- transition samples match the task modes in sequence;
- presence heartbeat failures remain zero;
- voice invocation failures remain zero when the optional voice gate is used.

These are process observations, not end-to-end sensory proof. The receipt keeps
compositor pixels, the physical display, physical audio and worker VRAM marked
unobserved. A compositor screenshot or human listening result must remain a
separate evidence artifact.
