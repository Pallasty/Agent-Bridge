#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
deploy_script="$script_dir/deploy-gte-int8-embedding.sh"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

cache="$test_root/cache"
config_home="$test_root/config"
stub_bin="$test_root/bin"
systemctl_log="$test_root/systemctl.log"
curl_count="$test_root/curl.count"
model=gte-multilingual-base

mkdir -p \
  "$cache/onnx-models/$model" \
  "$cache/onnx-models-int8/$model" \
  "$config_home" \
  "$stub_bin"

printf 'fp32 fixture\n' >"$cache/onnx-models/$model/model.onnx"
printf 'int8 fixture\n' >"$cache/onnx-models-int8/$model/model.onnx"
for file in tokenizer.json config.json special_tokens_map.json tokenizer_config.json; do
  printf '{}\n' >"$cache/onnx-models/$model/$file"
done

cat >"$stub_bin/systemctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$AB_TEST_SYSTEMCTL_LOG"
EOF

cat >"$stub_bin/curl" <<'EOF'
#!/usr/bin/env bash
count=0
if [ -f "$AB_TEST_CURL_COUNT" ]; then
  count="$(cat "$AB_TEST_CURL_COUNT")"
fi
count=$((count + 1))
printf '%s\n' "$count" >"$AB_TEST_CURL_COUNT"

if [ "$AB_TEST_EMBED_MODE" = recovers ] && [ "$count" -ge 2 ]; then
  /usr/bin/jq -cn '{backend:"gte-multilingual-base",dim:768,embedding:[range(768)|0]}'
else
  /usr/bin/jq -cn '{backend:"fnv1a-hash-384",dim:384,embedding:[range(384)|0]}'
fi
EOF

cat >"$stub_bin/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat >"$stub_bin/pgrep" <<'EOF'
#!/usr/bin/env bash
printf '12345\n'
EOF

cat >"$stub_bin/ps" <<'EOF'
#!/usr/bin/env bash
printf '102400\n'
EOF

chmod +x "$stub_bin/systemctl" "$stub_bin/curl" "$stub_bin/sleep" \
  "$stub_bin/pgrep" "$stub_bin/ps"

run_deploy() {
  local mode="$1"
  PATH="$stub_bin:$PATH" \
    AGENT_BRIDGE_ONNX_CACHE="$cache" \
    AGENT_BRIDGE_EMBED_REMOTE_URL="http://127.0.0.1:17878/embed" \
    XDG_CONFIG_HOME="$config_home" \
    AB_TEST_SYSTEMCTL_LOG="$systemctl_log" \
    AB_TEST_CURL_COUNT="$curl_count" \
    AB_TEST_EMBED_MODE="$mode" \
    bash "$deploy_script"
}

printf '0\n' >"$curl_count"
recovery_output="$(run_deploy recovers)"
printf '%s\n' "$recovery_output" | grep -Fq \
  'daemon-http /embed ready ({"backend":"gte-multilingual-base","dim":768,"vector_len":768})'
test "$(cat "$curl_count")" -eq 2

: >"$systemctl_log"
printf '0\n' >"$curl_count"
if fallback_output="$(run_deploy fallback 2>&1)"; then
  printf 'expected fallback-only deployment to fail\n' >&2
  exit 1
fi
printf '%s\n' "$fallback_output" | grep -Fq \
  'daemon-http /embed never became gte-multilingual-base/768d'
test "$(cat "$curl_count")" -eq 40
if grep -Fxq -- '--user restart agent-bridge-daemon.service' "$systemctl_log"; then
  printf 'daemon must not restart behind a fallback-only embed server\n' >&2
  exit 1
fi

printf 'PASS deploy-gte-int8 readiness gate\n'
