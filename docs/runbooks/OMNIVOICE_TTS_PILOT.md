# OmniVoice TTS default-off pilot

## Status

The OmniVoice ONNX candidate is wired into the synth-file Agent Bridge speech
entry as an explicit pilot backend. It is disabled by default, is not the
production default, and has no automatic Qwen fallback.

## Admission rules

- Set `AB_OMNIVOICE_TTS_ENABLED=1` explicitly for each pilot environment.
- Supply the isolated runtime with `--omnivoice-python` or
  `AB_OMNIVOICE_TTS_PYTHON`.
- Use `--voice auto`. Named speakers fail closed.
- Do not supply `--qwen-instruct`; style instructions fail closed on this
  backend instead of being silently discarded.
- The adapter fixes decoding to 32 steps and verifies every manifest component
  hash unless the underlying pinned bundle is deliberately changed.
- Use `--capture-channel synth_file` on Linux for this pilot. No live default or
  service configuration is changed by this runbook.

Example:

```bash
AB_OMNIVOICE_TTS_ENABLED=1 \
AB_OMNIVOICE_TTS_PYTHON=/Data/.venvs/qwen3-tts-cpu/bin/python \
/Data/.venvs/qwen3-tts-cpu/bin/python scripts/audio_embody.py \
  --mode speech \
  --capture-channel synth_file \
  --synth-backend omnivoice \
  --voice auto \
  --text '你好，欢迎使用本地语音助手。' \
  --json
```

The output receipt includes the manifest path/status, hash-verification result,
decode steps, language, runtime, and RTF. Playback success is not treated as
proof that a physical speaker was audible.

### Optional Mac execution host

The candidate can run on an explicitly configured Mac while the caller keeps
the existing canary and Qwen fallback logic. Remote execution is separately
default-off and requires all of the following settings:

```bash
AB_OMNIVOICE_TTS_ENABLED=1 \
AB_OMNIVOICE_MAC_REMOTE_ENABLED=1 \
AB_OMNIVOICE_MAC_REMOTE_HOST=user@mac-host \
AB_OMNIVOICE_MAC_REMOTE_PYTHON=/path/to/venv/bin/python \
AB_OMNIVOICE_MAC_REMOTE_ADAPTER=/path/to/agent-bridge/scripts/omnivoice_mac_remote_synth.py \
AB_OMNIVOICE_MAC_REMOTE_DISPATCH_PYTHON=/usr/bin/python3 \
python3 scripts/audio_embody.py \
  --mode speech --capture-channel synth_file --synth-backend omnivoice \
  --omnivoice-manifest /path/on/mac/composition-manifest.json \
  --voice auto --text '你好，欢迎使用远程语音执行节点。' --json
```

The dispatcher uses non-interactive SSH, sends request text as JSON on stdin,
copies back only the generated WAV, and removes its UUID-scoped remote job
directory. A non-blocking local lock admits one Mac decode at a time; lock,
timeout, SSH, manifest, or copy failures return a candidate error so the canary
router can execute its existing Qwen fallback policy. Host keys and SSH keys
must be provisioned outside this runbook.

## Verified smoke

The new Agent Bridge entry generated `你好。` as 1.20 seconds of 24 kHz mono
PCM16 audio. The manifest hashes passed, decode steps were 32, and RTF was
28.17. The durable receipt and WAV are under
`docs/reports/tts-comparison/omnivoice-pilot-entry-2026-08-15.*`.

The pilot remains unsuitable for named-character routes, instruction-controlled
delivery, or approved voice identity cloning. Those requests remain governed by
`config/tts-backend-capabilities.json` and the existing Qwen route.
