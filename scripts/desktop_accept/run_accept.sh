#!/usr/bin/env bash
# Cage acceptance E2E (Linux Computer Use, forum thread 79) — isolated.
#
# Proves an absolute target (x,y) -> click actually lands on the toy target's
# button, quantifying pixel accuracy of desktop_action.py's ISOLATED absolute
# backend (sway IPC). Zero host-desktop disturbance:
#   * a nested WAYLAND-backend sway is its own compositor (independent seat);
#     its seat gets pointer/keyboard caps from the parent, so `cursor set/press`
#     synthesize real wl_pointer events to the toy (a HEADLESS backend would
#     have seat caps=0 and clicks would never reach the client).
#   * swaymsg addresses via SWAYSOCK (NOT WAYLAND_DISPLAY) — we set the nested
#     socket explicitly and ABORT if it's bound to a host DP-*/HDMI-* output.
#   * desktop_action.py's sway-ipc backend independently refuses physical-output
#     sockets, so an "isolated" click can never leak onto the real desktop.
# The only host-visible effect is a transient nested window.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DA="$DIR/../desktop_action.py"
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
WLR_BACKENDS=wayland WLR_WL_OUTPUTS=1 WLR_RENDERER=pixman \
  sway -c "$CONF" >"$LOG" 2>&1 &
SWAY_PID=$!

disp=""
for i in $(seq 1 40); do
  if ! kill -0 "$SWAY_PID" 2>/dev/null; then echo "FAIL: nested sway died"; cat "$LOG"; exit 1; fi
  after=$(LC_ALL=C ls "$XDG_RUNTIME_DIR"/wayland-* 2>/dev/null | grep -v '\.lock$' | LC_ALL=C sort)
  disp=$(comm -13 <(echo "$before") <(echo "$after") | head -1)
  disp=${disp:+$(basename "$disp")}
  [ -n "$disp" ] && break
  sleep 0.25
done
[ -z "$disp" ] && { echo "FAIL: no nested display"; cat "$LOG"; exit 1; }

export WAYLAND_DISPLAY="$disp"
export SWAYSOCK="$XDG_RUNTIME_DIR/sway-ipc.$(id -u).$SWAY_PID.sock"
echo "== nested: pid=$SWAY_PID WAYLAND_DISPLAY=$disp SWAYSOCK_exists=$([ -S "$SWAYSOCK" ] && echo yes || echo NO)"
sleep 1.5

out_names=$(swaymsg -t get_outputs 2>/dev/null | python3 -c "import sys,json;print(','.join(o['name'] for o in json.load(sys.stdin)))" 2>/dev/null)
echo "== swaymsg-bound outputs: ${out_names:-NONE}"
case "$out_names" in
  *DP-*|*HDMI-*|"") echo "   [ABORT] bound to host/unknown ('${out_names:-NONE}') — refusing injection"; exit 2 ;;
  *) echo "   [OK] bound to nested compositor (non-host output)" ;;
esac
echo -n "== nested seat caps: "
swaymsg -t get_seats 2>/dev/null | python3 -c "import sys,json;[print(s['name'],'caps='+str(s.get('capabilities')),end=' ') for s in json.load(sys.stdin)]" 2>&1; echo

echo "== toy ready:"; cat "$STATE" 2>/dev/null; echo
grim "$WORK/shot_ready.png" 2>/dev/null && echo "   grim ready: $(stat -c%s "$WORK/shot_ready.png")B -> $WORK/shot_ready.png"

CX=670; CY=410
fmt='import sys,json;r=json.load(sys.stdin);print("     allowed=%s rc=%s detail=%s"%(r["allowed"],r.get("rc"),(r.get("detail") or "").replace(chr(10)," ")[:64]))'
echo "== inject via desktop_action.py (sway-ipc ISOLATED backend), target=$disp"
echo "   moveto $CX $CY:"; python3 "$DA" moveto "$CX" "$CY" --display "$disp" --swaysock "$SWAYSOCK" 2>&1 | python3 -c "$fmt" 2>&1
echo "   click left:";     python3 "$DA" click left      --display "$disp" --swaysock "$SWAYSOCK" 2>&1 | python3 -c "$fmt" 2>&1
sleep 0.6

echo "== toy AFTER:"; cat "$STATE" 2>/dev/null; echo
grim "$WORK/shot_after.png" 2>/dev/null && echo "   grim after: $(stat -c%s "$WORK/shot_after.png")B"

python3 -c "
import json
d=json.load(open('$STATE'))
if d.get('phase')=='clicked':
    print('== VERDICT:', 'HIT' if d['in_button'] else 'MISS')
    print('   click=%s target=%s dist=%.1fpx in_button=%s'%(tuple(d['click']),tuple(d['target_center']),d['dist_to_center'],d['in_button']))
    raise SystemExit(0 if d['in_button'] else 1)
print('== VERDICT: NO CLICK REGISTERED (phase=%s)'%d.get('phase')); raise SystemExit(1)
" 2>&1
