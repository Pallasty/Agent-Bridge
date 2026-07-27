#!/usr/bin/env bash
# Install the default-off Qwen3 persistent worker as an owner-local launchd agent.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uid="$(id -u)"
label="com.pallasting.agent-bridge.qwen3-tts"
lib_dir="$HOME/.local/lib/agent-bridge/qwen3-tts"
runtime_dir="$HOME/.cache/agent-bridge/qwen3"
plist="$HOME/Library/LaunchAgents/$label.plist"
python_bin="${AB_QWEN3_TTS_PYTHON:-$HOME/.local/share/agent-bridge/qwen3-tts-venv/bin/python}"
model_dir="${AB_QWEN3_TTS_MODEL:-$HOME/.cache/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master}"

[ -x "$python_bin" ] || { echo "missing isolated Qwen Python: $python_bin" >&2; exit 2; }
[ -d "$model_dir" ] || { echo "missing complete Qwen model: $model_dir" >&2; exit 2; }
mkdir -p "$lib_dir" "$runtime_dir" "$HOME/Library/LaunchAgents"
chmod 700 "$runtime_dir"
install -m 700 "$root/scripts/qwen3_tts_worker.py" "$lib_dir/qwen3_tts_worker.py"
install -m 700 "$root/scripts/qwen3_tts_synth.py" "$lib_dir/qwen3_tts_synth.py"

for old in "$plist"; do launchctl bootout "gui/$uid/$label" 2>/dev/null || true; done
sed -e "s|__PYTHON__|$python_bin|g" -e "s|__WORKER__|$lib_dir/qwen3_tts_worker.py|g" \
    -e "s|__SOCKET__|$runtime_dir/worker.sock|g" -e "s|__MODEL__|$model_dir|g" \
    -e "s|__LIB_DIR__|$lib_dir|g" -e "s|__LOG__|$runtime_dir/worker.log|g" \
    "$root/docs/deploy/com.pallasting.agent-bridge.qwen3-tts.plist.in" > "$plist"
plutil -lint "$plist" >/dev/null
launchctl bootstrap "gui/$uid" "$plist"
launchctl kickstart -k "gui/$uid/$label"
echo "worker socket: $runtime_dir/worker.sock"
echo "opt in: export AB_QWEN3_TTS_WORKER_SOCKET=$runtime_dir/worker.sock"
