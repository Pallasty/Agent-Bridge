#!/usr/bin/env bash
# Install the default-off Sherpa-ONNX TTS worker as an owner-local launchd agent.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uid="$(id -u)"
label="com.pallasting.agent-bridge.sherpa-tts"
lib_dir="$HOME/.local/lib/agent-bridge/sherpa-tts"
runtime_dir="$HOME/.cache/agent-bridge/sherpa"
plist="$HOME/Library/LaunchAgents/$label.plist"
model_dir="${AB_TTS_SHERPA_MODEL_DIR:-$HOME/.cache/agent-bridge/tts-models/vits-icefall-zh-aishell3}"
voice_map="${AB_TTS_SHERPA_VOICE_MAP:-speaker_66=66,speaker_21=21,speaker_45=45}"
threads="${AB_TTS_SHERPA_THREADS:-4}"
dtype="${AB_TTS_SHERPA_DTYPE:-unknown}"
source_bin="${AB_TTS_SHERPA_BIN:-$root/target/release/ab-sherpa-tts-synth}"

for asset in model.onnx lexicon.txt tokens.txt phone.fst date.fst number.fst; do
    [ -f "$model_dir/$asset" ] || { echo "missing Sherpa model asset: $model_dir/$asset" >&2; exit 2; }
done
case "$threads" in
    ''|*[!0-9]*) echo "AB_TTS_SHERPA_THREADS must be a positive integer" >&2; exit 2 ;;
    0) echo "AB_TTS_SHERPA_THREADS must be a positive integer" >&2; exit 2 ;;
esac
if [ ! -x "$source_bin" ] && [ -z "${AB_TTS_SHERPA_BIN:-}" ]; then
    cargo build --release -p ab-tts --features sherpa --bin ab-sherpa-tts-synth \
        --manifest-path "$root/Cargo.toml"
fi
[ -x "$source_bin" ] || { echo "missing Sherpa worker binary: $source_bin" >&2; exit 2; }

mkdir -p "$lib_dir" "$runtime_dir" "$HOME/Library/LaunchAgents"
chmod 700 "$runtime_dir"
install -m 700 "$source_bin" "$lib_dir/ab-sherpa-tts-synth"

launchctl bootout "gui/$uid/$label" 2>/dev/null || true
sed -e "s|__BINARY__|$lib_dir/ab-sherpa-tts-synth|g" \
    -e "s|__SOCKET__|$runtime_dir/worker.sock|g" \
    -e "s|__MODEL__|$model_dir|g" \
    -e "s|__VOICE_MAP__|$voice_map|g" \
    -e "s|__THREADS__|$threads|g" \
    -e "s|__DTYPE__|$dtype|g" \
    -e "s|__LIB_DIR__|$lib_dir|g" \
    -e "s|__LOG__|$runtime_dir/worker.log|g" \
    "$root/docs/deploy/com.pallasting.agent-bridge.sherpa-tts.plist.in" > "$plist"
plutil -lint "$plist" >/dev/null
launchctl bootstrap "gui/$uid" "$plist"
launchctl kickstart -k "gui/$uid/$label"
worker_ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if [ -S "$runtime_dir/worker.sock" ] && python3 "$root/scripts/validate_tts_worker_contract.py" \
        --socket "$runtime_dir/worker.sock" \
        --expected-engine sherpa-onnx \
        --require-capability zh \
        --require-capability multi_speaker >/dev/null 2>&1; then
        worker_ready=1
        break
    fi
    sleep 0.2
done
[ "$worker_ready" -eq 1 ] || {
    echo "Sherpa worker did not become healthy; inspect $runtime_dir/worker.log" >&2
    exit 3
}
echo "worker socket: $runtime_dir/worker.sock"
echo "explicit opt in: --synth-backend sherpa --sherpa-worker $runtime_dir/worker.sock"
