# Voice embodiment re-closure

This runbook restores a version-matched Agent-Bridge voice composition without
silently widening the default MCP surface or treating self-readback as general
hearing.

## Boundaries

- `voice_runtime_preflight` checks configuration only. It never synthesizes,
  plays, records, downloads, restarts, or changes runtime state.
- `synth_file` + STT verifies intelligibility of the generated file, not
  playback.
- `sink_monitor` verifies delivery to the output bus, not the transducer.
- `mic` verifies that one microphone heard acoustic output in the air. It is
  not continuous environmental perception and does not prove a listener heard
  private headphone output.
- `present_voice_confirm_audibility` records one human report about one named
  outcome. It does not generalize to future runs.

## Install a matched binary and adapter

`scripts/deploy_from_master.sh` installs `agent-bridge.real` and the repository
copy of `scripts/audio_embody.py` in one gated operation. By default the adapter
is installed at:

```text
~/.local/share/ab-tts/audio_embody.py
```

The wrapper points `AGENT_BRIDGE_AUDIO_EMBODY_SCRIPT` there. The deploy backs
up both the prior binary and prior adapter and verifies byte equality after the
copy.

Use `--dry-run` before an authorized deployment. Deployment and MCP reconnect
remain separate explicit operator actions.

## Opt in one Codex client

Set the MCP server's toolset to:

```text
AGENT_BRIDGE_TOOLSET=codex-voice
AGENT_BRIDGE_TOOL_PROFILE=essential
```

`codex-voice` is the compact `codex-essential` surface plus exactly:

- `present_voice`
- `present_voice_confirm_audibility`
- `voice_runtime_preflight`
- `voice_delivery_health`
- `embodiment_operating_readiness`

It does not expose unrelated Niche browser, desktop, or presentation mutation.
An already-running MCP client must reconnect before its tool manifest changes.

## Verification order

1. Call `voice_runtime_preflight` for the exact backend and channel.
2. If file intelligibility is required, run the explicit `synth_file` rung.
3. If Linux output-bus delivery is required, run `sink_monitor`.
4. If speaker-to-air delivery is required and microphone recording is
   authorized, run `mic`.
5. If a person evaluated one outcome, record that statement separately with
   `present_voice_confirm_audibility`.

Never skip directly from configuration readiness or playback exit status to a
human-audibility claim.

## User speech remains out of scope

This lane does not provide continuous listening or a mic-to-dialogue path.
User speech input requires a separate design covering capture consent, VAD,
ASR, provenance, retention, interruption semantics, and dialogue injection.
