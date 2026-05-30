#!/usr/bin/env bash
# Host-confirm path A for desktop_action (coordinate input) — two-phase acceptance.
# (Linux Computer Use, thread 79; design docs/design/HOST_CONFIRM_PATH.md)
#
# Mirrors run_hostconfirm_accept.sh (invoke) for the COORDINATE tool. A cage click
# on the toy target is the observable; the cage is treated as "host" only for the
# click under test by pointing AB_HOST_WAYLAND_DISPLAY at the nested display — so
# the gate sees is_host=True while the injection stays cage-confined via sway-ipc.
#
#   pre   isolated moveto positions the cage cursor over the toy button (no confirm).
#   A. click --request-host-confirm  -> pending token, NOTHING injected (toy clicks==0).
#   B. --confirm-token <tok>         -> click lands -> toy clicks==1, in_button.
#   C. --confirm-token <tok> (again) -> DENIED (single-use), toy clicks unchanged.
#   D. plain host click (no request)  -> DENIED rc=3 (default closed), toy unchanged.
#   E. an ACTION token confirmed via desktop_invoke.py -> rejected (kind guard).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DA="$DIR/../desktop_action.py"
INV="$DIR/../desktop_invoke.py"
TOY="$DIR/toy_target.py"
STATE="$HOME/.cache/agent-bridge/cage_toy_hit.json"
WORK="$(mktemp -d)"; LOG="$WORK/sway.log"; CONF="$WORK/sway.conf"
SWAY_PID=""
cleanup() { [ -n "$SWAY_PID" ] && kill "$SWAY_PID" 2>/dev/null; wait "$SWAY_PID" 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT
rm -f "$STATE"

cat >"$CONF" <<EOF
output * resolution 1280x800 position 0 0
default_border none
hide_edge_borders both
bar mode invisible
exec python3 $TOY
bindsym Mod4+Shift+q exit
EOF

before=$(LC_ALL=C ls "$XDG_RUNTIME_DIR"/wayland-* 2>/dev/null | grep -v '\.lock$' | LC_ALL=C sort)
WLR_BACKENDS=wayland WLR_WL_OUTPUTS=1 WLR_RENDERER=pixman sway -c "$CONF" >"$LOG" 2>&1 &
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
out_names=$(swaymsg -t get_outputs 2>/dev/null | python3 -c "import sys,json;print(','.join(o['name'] for o in json.load(sys.stdin)))" 2>/dev/null)
case "$out_names" in *DP-*|*HDMI-*|"") echo "[ABORT] bound to host/unknown output '${out_names:-NONE}'"; exit 2 ;; esac
echo "== nested sway pid=$SWAY_PID disp=$disp outputs=$out_names =="
sleep 2

CX=670; CY=410
field() { python3 -c "import json,sys;print(json.load(sys.stdin).get('$1'))" 2>/dev/null; }
clicks() { python3 -c "import json;print(json.load(open('$STATE')).get('clicks',-1))" 2>/dev/null; }

echo "== pre: isolated moveto $CX $CY (nested != host wayland-1 -> isolated, positions cursor) =="
python3 "$DA" moveto "$CX" "$CY" --display "$disp" --swaysock "$SWAYSOCK" 2>&1 | field allowed | sed 's/^/   moveto allowed=/'
echo "   toy clicks before any confirm: $(clicks)"

# From here the cage is treated as "host" for the click under test.
export AB_HOST_WAYLAND_DISPLAY="$disp"

echo "== A. phase 1: click --request-host-confirm -> pending, NOTHING injected =="
A=$(python3 "$DA" click left --display "$disp" --swaysock "$SWAYSOCK" --request-host-confirm 2>&1); echo "   $A"
A_pending=$(echo "$A" | field pending); A_allowed=$(echo "$A" | field allowed); TOKEN=$(echo "$A" | field token)
sleep 0.5; A_clicks=$(clicks)
echo "   -> pending=$A_pending allowed=$A_allowed token=${TOKEN:0:8}… toy_clicks=$A_clicks (must be true/false/<tok>/0)"

echo "== B. phase 2: --confirm-token executes -> click lands on toy =="
B=$(python3 "$DA" --confirm-token "$TOKEN" 2>&1); echo "   $B"
B_allowed=$(echo "$B" | field allowed); B_rc=$(echo "$B" | field rc)
sleep 0.8; B_clicks=$(clicks); B_inbtn=$(python3 -c "import json;print(json.load(open('$STATE')).get('in_button'))" 2>/dev/null)
echo "   -> allowed=$B_allowed rc=$B_rc toy_clicks=$B_clicks in_button=$B_inbtn (must be true/0/1/True)"

echo "== C. replay same token -> DENIED (single-use) =="
C=$(python3 "$DA" --confirm-token "$TOKEN" 2>&1); echo "   $C"
C_allowed=$(echo "$C" | field allowed); C_rc=$(echo "$C" | field rc); C_clicks=$(clicks)
echo "   -> allowed=$C_allowed rc=$C_rc toy_clicks=$C_clicks (must be false/3/1)"

echo "== D. plain host click (no request-host-confirm) -> DENIED rc=3 (default closed) =="
D=$(python3 "$DA" click left --display "$disp" --swaysock "$SWAYSOCK" 2>&1); echo "   $D"
D_allowed=$(echo "$D" | field allowed); D_clicks=$(clicks)
echo "   -> allowed=$D_allowed toy_clicks=$D_clicks (must be false/1)"

echo "== E. kind guard: confirm an ACTION token via desktop_invoke.py -> rejected =="
E_STAGE=$(python3 "$DA" click left --display "$disp" --swaysock "$SWAYSOCK" --request-host-confirm 2>&1)
E_TOKEN=$(echo "$E_STAGE" | field token)
E=$(python3 "$INV" --confirm-token "$E_TOKEN" 2>&1); echo "   $E"
E_allowed=$(echo "$E" | field allowed); E_err=$(echo "$E" | python3 -c "import json,sys;print(json.load(sys.stdin).get('error',''))" 2>/dev/null)
echo "   -> allowed=$E_allowed error='$E_err' (must be false + mentions kind/invoke)"

echo "== VERDICT =="
python3 - "$A_pending" "$A_allowed" "$TOKEN" "$A_clicks" "$B_allowed" "$B_rc" "$B_clicks" "$B_inbtn" \
            "$C_allowed" "$C_rc" "$C_clicks" "$D_allowed" "$D_clicks" "$E_allowed" "$E_err" <<'PY'
import sys
(A_pending,A_allowed,TOKEN,A_clicks,B_allowed,B_rc,B_clicks,B_inbtn,
 C_allowed,C_rc,C_clicks,D_allowed,D_clicks,E_allowed,E_err) = sys.argv[1:16]
checks = [
  ("A phase1 pending==true",               A_pending=="True"),
  ("A phase1 allowed==false",              A_allowed=="False"),
  ("A phase1 token minted",                bool(TOKEN) and TOKEN not in ("None","")),
  ("A phase1 injected NOTHING (clicks==0)", A_clicks=="0"),
  ("B phase2 allowed==true",               B_allowed=="True"),
  ("B phase2 rc==0",                       B_rc=="0"),
  ("B phase2 click landed (clicks==1)",    B_clicks=="1"),
  ("B phase2 hit the button (in_button)",  B_inbtn=="True"),
  ("C replay DENIED single-use",           C_allowed=="False" and C_rc=="3"),
  ("C replay injected nothing (clicks==1)", C_clicks=="1"),
  ("D default host click DENIED",          D_allowed=="False"),
  ("D default injected nothing (clicks==1)", D_clicks=="1"),
  ("E action token rejected by invoke (kind guard)", E_allowed=="False" and ("kind" in E_err or "invoke" in E_err or "action" in E_err)),
]
ok=True
for label,passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — desktop_action two-phase host-confirm: stage/execute/single-use/default-closed/kind-guard" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
