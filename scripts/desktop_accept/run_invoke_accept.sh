#!/usr/bin/env bash
# Cage AT-SPI INVOKE acceptance (Linux Computer Use, forum thread 79) — isolated.
#
# Proves desktop_invoke activates a real Gtk.Button via AT-SPI Action.do_action
# with ZERO coordinates (no screenshot, no OCR), and that its gate matches
# desktop_action's posture using a PID-subtree isolation primitive:
#   A. isolated invoke (--cage-pid = nested sway) -> ALLOWED, button activates.
#   B. --dry-run                                  -> ALLOWED, NO activation.
#   C. no --cage-pid, no --confirm (host posture) -> DENIED,  NO activation.
#   D. desktop_semantic_task MCP transaction         -> snapshot + invoke + verify.
#
# Optional evidence controls:
#   AB_ACCEPT_RECEIPT_PATH=/durable/path/receipt.json
#       Write and validate agent_bridge.desktop_acceptance_receipt.v0.
#   AB_ACCEPT_WLR_BACKEND=headless
#       Use a virtual headless wlroots backend when no parent Wayland display
#       exists. The default remains the nested Wayland backend.
#   AB_ACCEPT_SOURCE_COMMIT=<40-64 lowercase hex>
#       Bind a staged source/script bundle that is outside a Git checkout.
#
# AT-SPI is a session-global D-Bus registry, so desktop_invoke runs in the HOST
# env (display-independent) and isolates by process: the toy is exec'd by the
# nested sway, so its app PID is a descendant of $SWAY_PID.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../.." && pwd)"
INV="$DIR/../desktop_invoke.py"
SNAP="$DIR/../desktop_snapshot.py"
VERIFY="$DIR/../desktop_verify.py"
TOY="$DIR/toy_button.py"
RECEIPT="$DIR/desktop_acceptance_receipt.py"
STATE="$HOME/.cache/agent-bridge/cage_invoke_hit.json"
WORK="$(mktemp -d)"; LOG="$WORK/sway.log"; CONF="$WORK/sway.conf"
SWAY_PID=""
cleanup() { [ -n "$SWAY_PID" ] && kill "$SWAY_PID" 2>/dev/null; wait "$SWAY_PID" 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT
rm -f "$STATE"

cat >"$CONF" <<EOF
default_border none
hide_edge_borders both
bar mode invisible
exec env GTK_A11Y=atk-bridge NO_AT_BRIDGE=0 python3 $TOY
bindsym Mod4+Shift+q exit
EOF

before=$(LC_ALL=C ls "$XDG_RUNTIME_DIR"/wayland-* 2>/dev/null | grep -v '\.lock$' | LC_ALL=C sort)
ACCEPT_BACKEND="${AB_ACCEPT_WLR_BACKEND:-wayland}"
case "$ACCEPT_BACKEND" in
  wayland)
    WLR_BACKENDS=wayland WLR_WL_OUTPUTS=1 WLR_RENDERER=pixman sway -c "$CONF" >"$LOG" 2>&1 &
    ;;
  headless)
    WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1 WLR_RENDERER=pixman sway -c "$CONF" >"$LOG" 2>&1 &
    ;;
  *)
    echo "FAIL: AB_ACCEPT_WLR_BACKEND must be wayland or headless (got '$ACCEPT_BACKEND')"
    exit 2
    ;;
esac
SWAY_PID=$!
disp=""
for i in $(seq 1 40); do
  if ! kill -0 "$SWAY_PID" 2>/dev/null; then echo "FAIL: nested sway died"; cat "$LOG"; exit 1; fi
  after=$(LC_ALL=C ls "$XDG_RUNTIME_DIR"/wayland-* 2>/dev/null | grep -v '\.lock$' | LC_ALL=C sort)
  disp=$(comm -13 <(echo "$before") <(echo "$after") | head -1); disp=${disp:+$(basename "$disp")}
  [ -n "$disp" ] && break
  sleep 0.25
done
[ -z "$disp" ] && { echo "FAIL: no nested display"; cat "$LOG"; exit 1; }
export SWAYSOCK="$XDG_RUNTIME_DIR/sway-ipc.$(id -u).$SWAY_PID.sock"
# defense-in-depth: refuse if the nested sway somehow bound a physical output
out_names=$(swaymsg -t get_outputs 2>/dev/null | python3 -c "import sys,json;print(','.join(o['name'] for o in json.load(sys.stdin)))" 2>/dev/null)
case "$out_names" in *DP-*|*HDMI-*) echo "[ABORT] bound to host output '$out_names'"; exit 2 ;; esac
echo "== nested sway pid=$SWAY_PID disp=$disp outputs=${out_names:-?}"
echo "== nested sway backend=$ACCEPT_BACKEND"
sleep 3
echo "== toy ready: $(cat "$STATE" 2>/dev/null)"

SEL=(--app toy_button --role button --name INVOKE_TARGET)  # AT-SPI role name is "button" (not "push button")
acts() { python3 -c "import json;print(json.load(open('$STATE')).get('activations',-1))" 2>/dev/null; }
field() { python3 -c "import json,sys;print(json.load(sys.stdin).get('$1'))" 2>/dev/null; }

echo "== 0. snapshot observes the target before acting =="
S=$(python3 "$SNAP" --no-screenshot --activate-a11y --a11y-settle 1 --compact 2>&1)
S_present=$(echo "$S" | python3 -c '
import json,sys
s=json.load(sys.stdin)
apps=(s.get("atspi") or {}).get("apps") or s.get("apps") or []
print(any("toy_button" in (a.get("name") or "") and any("INVOKE_TARGET" in (e.get("name") or "") for e in (a.get("elements") or [])) for a in apps))' 2>/dev/null)
echo "   -> target_present=$S_present"
if [ "$S_present" != "True" ]; then
  echo "   snapshot payload: $S"
fi

echo "== A. isolated invoke (--cage-pid $SWAY_PID) =="
A=$(python3 "$INV" "${SEL[@]}" --cage-pid "$SWAY_PID" 2>&1); echo "   $A"
A_allowed=$(echo "$A" | field allowed); A_rc=$(echo "$A" | field rc); A_iso=$(echo "$A" | python3 -c "import json,sys;print(json.load(sys.stdin).get('found',{}).get('isolated'))" 2>/dev/null)
A_acts=$(acts)
echo "   -> allowed=$A_allowed rc=$A_rc isolated=$A_iso activations=$A_acts"

echo "== A2. verify re-observes the isolated target after acting =="
V=$(python3 "$VERIFY" --expect element_appeared "${SEL[@]}" --cage-pid "$SWAY_PID" --timeout 2 --compact 2>&1); echo "   $V"
V_verdict=$(echo "$V" | field verdict); V_recover=$(echo "$V" | field recover)
echo "   -> verdict=$V_verdict recover=$V_recover"

echo "== B. dry-run (no cage-pid) =="
B=$(python3 "$INV" "${SEL[@]}" --dry-run 2>&1); echo "   $B"
B_allowed=$(echo "$B" | field allowed); B_acts=$(acts)
echo "   -> allowed=$B_allowed activations=$B_acts (must be unchanged = $A_acts)"

echo "== C. host posture (no cage-pid, no confirm) -> must DENY =="
C=$(python3 "$INV" "${SEL[@]}" 2>&1); echo "   $C"
C_allowed=$(echo "$C" | field allowed); C_acts=$(acts)
echo "   -> allowed=$C_allowed activations=$C_acts (must be unchanged = $A_acts)"

echo "== D. one-call desktop_semantic_task transaction =="
AB_BIN="${AB_MCP_BIN:-$ROOT/target/debug/agent-bridge}"
if [ ! -x "$AB_BIN" ]; then
  echo "FAIL: MCP binary not executable at $AB_BIN (build it or set AB_MCP_BIN)"
  exit 1
fi
MCP_IN="$WORK/semantic-task.in.jsonl"
MCP_OUT="$WORK/semantic-task.out.jsonl"
MCP_ERR="$WORK/semantic-task.stderr"
python3 - "$MCP_IN" "$SWAY_PID" "$ROOT" "$SWAYSOCK" <<'PY'
import json
import sys

path, cage_pid, cwd, swaysock = sys.argv[1:5]
messages = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "desktop-semantic-task-accept", "version": "1"},
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "desktop_semantic_task",
            "arguments": {
                "app": "toy_button",
                "role": "button",
                "name": "INVOKE_TARGET",
                "cage_pid": int(cage_pid),
                "expect": "element_appeared",
                "swaysock": swaysock,
                "cwd": cwd,
                "snapshot_timeout_ms": 15000,
                "invoke_timeout_ms": 10000,
                "verify_timeout_ms": 10000,
                "poll_timeout_secs": 2,
            },
        },
    },
]
with open(path, "w", encoding="utf-8") as handle:
    for message in messages:
        handle.write(json.dumps(message) + "\n")
PY
timeout 60 env \
  AGENT_BRIDGE_TOOLSET=codex-essential \
  AGENT_BRIDGE_DB="$WORK/agent-bridge.sqlite" \
  "$AB_BIN" mcp <"$MCP_IN" >"$MCP_OUT" 2>"$MCP_ERR" || true
D=$(python3 - "$MCP_OUT" <<'PY'
import json
import sys

for line in open(sys.argv[1], encoding="utf-8"):
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        continue
    if message.get("id") != 2:
        continue
    if message.get("error"):
        print(json.dumps({"status": "mcp_error", "error": message["error"]}))
        break
    for block in (message.get("result") or {}).get("content") or []:
        if block.get("type") == "text":
            try:
                print(json.dumps(json.loads(block.get("text") or "{}")))
            except json.JSONDecodeError:
                print(json.dumps({"status": "invalid_text_json"}))
            raise SystemExit
    print(json.dumps({"status": "missing_text_result"}))
    break
else:
    print(json.dumps({"status": "missing_call_response"}))
PY
)
echo "   $D"
D_status=$(echo "$D" | field status)
D_verdict=$(echo "$D" | field verdict)
D_recover=$(echo "$D" | field recover)
D_mode=$(echo "$D" | python3 -c "import json,sys;print((json.load(sys.stdin).get('safety') or {}).get('mode'))" 2>/dev/null)
D_acts=$(acts)
echo "   -> status=$D_status verdict=$D_verdict recover=$D_recover mode=$D_mode activations=$D_acts"
if [ "$D_status" != "verified" ]; then
  echo "   MCP stderr: $(tail -c 2000 "$MCP_ERR" 2>/dev/null)"
fi

echo "== VERDICT =="
verdict_rc=0
python3 - "$S_present" "$A_allowed" "$A_rc" "$A_iso" "$A_acts" "$V_verdict" "$V_recover" "$B_allowed" "$B_acts" "$C_allowed" "$C_acts" "$D_status" "$D_verdict" "$D_recover" "$D_mode" "$D_acts" <<'PY'
import sys
S_present,A_allowed,A_rc,A_iso,A_acts,V_verdict,V_recover,B_allowed,B_acts,C_allowed,C_acts,D_status,D_verdict,D_recover,D_mode,D_acts = sys.argv[1:17]
ok = True
checks = [
  ("0 snapshot sees target", S_present=="True"),
  ("A isolated invoke allowed", A_allowed=="True"),
  ("A rc==0", A_rc=="0"),
  ("A isolated==True", A_iso=="True"),
  ("A activated button (activations==1)", A_acts=="1"),
  ("A2 verify postcondition", V_verdict=="verified"),
  ("A2 recover says proceed", V_recover=="proceed"),
  ("B dry-run allowed", B_allowed=="True"),
  ("B no extra activation", B_acts=="1"),
  ("C host invoke DENIED", C_allowed=="False"),
  ("C no activation", C_acts=="1"),
  ("D transaction status verified", D_status=="verified"),
  ("D transaction verdict verified", D_verdict=="verified"),
  ("D transaction recover proceed", D_recover=="proceed"),
  ("D transaction mode isolated", D_mode=="isolated"),
  ("D transaction activated once", D_acts=="2"),
]
for label, passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — low-level invoke + one-call semantic task isolated and verified" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
verdict_rc=$?

receipt_rc=0
if [ -n "${AB_ACCEPT_RECEIPT_PATH:-}" ]; then
  printf '%s\n' "$A" >"$WORK/isolated-invoke.json"
  printf '%s\n' "$V" >"$WORK/postcondition-verify.json"
  printf '%s\n' "$B" >"$WORK/dry-run-invoke.json"
  printf '%s\n' "$C" >"$WORK/host-invoke.json"
  printf '%s\n' "$D" >"$WORK/semantic-task.json"
  source_commit="${AB_ACCEPT_SOURCE_COMMIT:-}"
  if [ -z "$source_commit" ]; then
    source_commit=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)
  fi
  binary_version=$("$AB_BIN" --version 2>/dev/null || true)
  snapshot_target_present=false
  [ "$S_present" = "True" ] && snapshot_target_present=true
  python3 "$RECEIPT" write \
    --output "$AB_ACCEPT_RECEIPT_PATH" \
    --source-commit "$source_commit" \
    --binary "$AB_BIN" \
    --binary-version "$binary_version" \
    --backend "$ACCEPT_BACKEND" \
    --output-names "$out_names" \
    --display "$disp" \
    --sway-pid "$SWAY_PID" \
    --snapshot-target-present "$snapshot_target_present" \
    --isolated-invoke "$WORK/isolated-invoke.json" \
    --postcondition-verify "$WORK/postcondition-verify.json" \
    --dry-run-invoke "$WORK/dry-run-invoke.json" \
    --host-invoke "$WORK/host-invoke.json" \
    --semantic-task "$WORK/semantic-task.json" \
    --isolated-activations "$A_acts" \
    --dry-run-activations "$B_acts" \
    --host-activations "$C_acts" \
    --transaction-activations "$D_acts"
  receipt_rc=$?
fi

[ "$verdict_rc" -eq 0 ] || exit "$verdict_rc"
exit "$receipt_rc"
