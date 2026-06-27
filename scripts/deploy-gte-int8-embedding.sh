#!/usr/bin/env bash
# Per-node deploy of the gte-768 embedding RAM reduction. Run AFTER the agent-bridge
# binary is updated (scripts/deploy_from_master.sh) so this node realizes the same
# ~2.28GB cut measured on the origin node:
#
#   fp32 double-load   daemon 1763 + daemon-http 1759 = ~3522 MB
#   embedding int8     daemon 1217 + daemon-http 1219 = ~2436 MB
#   + daemon delegate  daemon   26 + daemon-http 1217 = ~1243 MB   (lossless)
#
# Two levers, both applied here:
#   1. embedding-only INT8 gte model (Gather op int8, transformer fp32) — served by
#      daemon-http; cos 0.9997 / recall@10 0.980 vs fp32 (see quantize_gte_embedding_int8.py).
#   2. opt-in daemon -> daemon-http embedding delegation (the daemon stops loading its
#      own model copy). Requires the binary built from the daemon-embed-delegation change.
#
# Mechanism: systemd --user drop-ins. They override machine.env's guarded
# `${VAR:-default}` exports because systemd sets Environment= BEFORE the wrapper
# sources machine.env. The fp32 bundle is left untouched -> fully reversible.
#
# Idempotent. Reversible: `deploy-gte-int8-embedding.sh --rollback`.
# Assumes the standard topology: systemd --user units agent-bridge-daemon +
# agent-bridge-daemon-http, with daemon-http serving /embed on 127.0.0.1:7878.
set -euo pipefail

MODEL=gte-multilingual-base
CACHE="${AGENT_BRIDGE_ONNX_CACHE:-$HOME/.cache/agent-bridge}"
FP32_DIR="$CACHE/onnx-models/$MODEL"
INT8_BASE="$CACHE/onnx-models-int8"
INT8_DIR="$INT8_BASE/$MODEL"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
EMBED_URL="${AGENT_BRIDGE_EMBED_REMOTE_URL:-http://127.0.0.1:7878/embed}"
DROPIN=int8-model.conf
HERE="$(cd "$(dirname "$0")" && pwd)"

say() { printf '>> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

rollback() {
  say "rollback: removing int8 drop-ins, reload + restart (back to fp32 model, no delegation)"
  rm -f "$UNIT_DIR/agent-bridge-daemon.service.d/$DROPIN" \
        "$UNIT_DIR/agent-bridge-daemon-http.service.d/$DROPIN"
  systemctl --user daemon-reload
  systemctl --user restart agent-bridge-daemon-http.service agent-bridge-daemon.service
  say "done. int8 model dir left at $INT8_DIR (delete manually to reclaim disk)."
  exit 0
}
[ "${1:-}" = "--rollback" ] && rollback

[ -f "$FP32_DIR/model.onnx" ] || die "fp32 model not found at $FP32_DIR — is gte deployed on this node?"

# 1) generate the embedding-only int8 model if missing
if [ -f "$INT8_DIR/model.onnx" ]; then
  say "int8 model already present: $INT8_DIR/model.onnx ($(stat -c%s "$INT8_DIR/model.onnx" 2>/dev/null || echo '?') bytes)"
else
  say "generating embedding-only int8 model (one-time) ..."
  mkdir -p "$INT8_DIR"
  venv="$CACHE/.int8-quant-venv"
  if [ ! -x "$venv/bin/python" ]; then
    say "bootstrapping a python env with onnxruntime ..."
    if command -v uv >/dev/null 2>&1; then
      uv venv --python 3.12 "$venv" >/dev/null
      VIRTUAL_ENV="$venv" uv pip install -q onnxruntime onnx >/dev/null
    elif command -v python3 >/dev/null 2>&1; then
      python3 -m venv "$venv"
      "$venv/bin/pip" install -q --upgrade pip >/dev/null
      "$venv/bin/pip" install -q onnxruntime onnx >/dev/null
    else
      die "no uv or python3 to build a quantization env. Alternative: copy $INT8_DIR/model.onnx from a node that has it, then re-run."
    fi
  fi
  "$venv/bin/python" "$HERE/quantize_gte_embedding_int8.py" "$FP32_DIR/model.onnx" "$INT8_DIR/model.onnx" \
    || die "quantization failed. Alternative: copy $INT8_DIR/model.onnx from a node that has it, then re-run."
  for f in tokenizer.json config.json special_tokens_map.json tokenizer_config.json; do
    cp -f "$FP32_DIR/$f" "$INT8_DIR/$f"
  done
  say "int8 model ready ($(stat -c%s "$INT8_DIR/model.onnx") bytes)"
fi

# 2) systemd drop-ins
say "writing systemd drop-ins under $UNIT_DIR ..."
mkdir -p "$UNIT_DIR/agent-bridge-daemon.service.d" "$UNIT_DIR/agent-bridge-daemon-http.service.d"
# daemon: serve int8 on the fallback path AND delegate embeds to daemon-http (the dedup lever)
cat > "$UNIT_DIR/agent-bridge-daemon.service.d/$DROPIN" <<EOF
# gte embedding RAM reduction (see scripts/deploy-gte-int8-embedding.sh).
# int8 model for the local fallback path + opt-in delegation to daemon-http /embed.
[Service]
Environment=AGENT_BRIDGE_ONNX_MODEL_DIR=$INT8_BASE
Environment=AGENT_BRIDGE_EMBED_REMOTE_URL=$EMBED_URL
EOF
# daemon-http: the shared /embed server — serve the int8 model locally. It must
# NEVER delegate (the DaemonHttp arm does not call install_if_configured, so even
# if it inherits AGENT_BRIDGE_EMBED_REMOTE_URL from machine.env it cannot self-loop).
cat > "$UNIT_DIR/agent-bridge-daemon-http.service.d/$DROPIN" <<EOF
# gte embedding RAM reduction: serve the embedding-only int8 model.
[Service]
Environment=AGENT_BRIDGE_ONNX_MODEL_DIR=$INT8_BASE
EOF

# 3) reload + restart (server first so the delegating daemon finds it) + verify
say "daemon-reload + restart (daemon-http first, then daemon) ..."
systemctl --user daemon-reload
systemctl --user restart agent-bridge-daemon-http.service
for _ in $(seq 1 40); do
  bk=$(curl -s --max-time 30 "$EMBED_URL" -H 'content-type: application/json' -d '{"text":"setup warmup"}' 2>/dev/null | grep -o '"backend":"[^"]*"' || true)
  [ -n "$bk" ] && { say "daemon-http /embed ready ($bk)"; break; }
  sleep 1
done
systemctl --user restart agent-bridge-daemon.service
sleep 6

dpid=$(pgrep -f 'agent-bridge.real daemon$' | head -1 || true)
hpid=$(pgrep -f 'agent-bridge.real daemon-http' | head -1 || true)
drss=$(ps -o rss= -p "${dpid:-0}" 2>/dev/null | awk '{print int($1/1024)}'); drss=${drss:-0}
hrss=$(ps -o rss= -p "${hpid:-0}" 2>/dev/null | awk '{print int($1/1024)}'); hrss=${hrss:-0}
say "RSS: daemon=${drss}MB (pid ${dpid:-none})  daemon-http=${hrss}MB (pid ${hpid:-none})"
if [ "$drss" -gt 0 ] && [ "$drss" -lt 800 ]; then
  say "PASS: daemon is delegating (no local model load)."
else
  say "NOTE: daemon RSS=${drss}MB is high — daemon-http may be unreachable, so the daemon"
  say "      fell back to a local model load (correctness kept, RAM sharing degraded)."
  say "      Check: journalctl --user -u agent-bridge-daemon -n 50, and ~/.cache/agent-bridge/daemon.log"
fi
say "DONE. Sanity: curl -s $EMBED_URL -H 'content-type: application/json' -d '{\"text\":\"hi\"}'"
say "Rollback: $0 --rollback"
