#!/usr/bin/env bash
# Cage GROUNDING acceptance E2E (Linux Computer Use, forum thread 79) — isolated.
#
# Extends run_accept.sh from "known hardcoded target (670,410)" to a coordinate
# DERIVED from the vision-grounding pipeline:
#
#   nested sway + toy  ->  grim screenshot
#     ->  vision_grounding_ocr.py --engine fixture-tsv  (fixture = cairo-measured
#         ground-truth ink box of the toy's "CLICK_TARGET" text; see
#         gen_fixture_tsv.py for why this is honest, not a hand-picked coord)
#     ->  pick the candidate matching --hint-text CLICK_TARGET, take its center
#     ->  desktop_action.py moveto <center> + click  (sway-ipc ISOLATED backend)
#     ->  toy self-reports the click; assert it landed INSIDE the button.
#
# This closes the vision half of the loop: snapshot -> grounding -> action -> hit,
# with the click coordinate produced by grounding rather than hardcoded. The only
# part still stubbed is tesseract's *recognition* (blocked on apt install); the
# bbox->center->isolated-click->hit wiring + coordinate math are proven live.
#
# Same isolation guarantees as run_accept.sh: WAYLAND-backend nested sway, explicit
# nested SWAYSOCK, ABORT if bound to a host DP-*/HDMI-* output, and desktop_action
# independently refusing physical-output sockets.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DA="$DIR/../desktop_action.py"
VG="$DIR/../vision_grounding_ocr.py"
TOY="$DIR/toy_target.py"
GEN="$DIR/gen_fixture_tsv.py"
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

echo "== toy ready:"; cat "$STATE" 2>/dev/null; echo
SHOT="$WORK/shot_ready.png"
grim "$SHOT" 2>/dev/null && echo "   grim ready: $(stat -c%s "$SHOT")B -> $SHOT"

# ---- GROUNDING: fixture-TSV -> vision_grounding_ocr -> center ----
FIX="$WORK/fixture.tsv"
python3 "$GEN" >"$FIX" 2>"$WORK/fixture.err"
echo "== fixture TSV (cairo-measured ground truth): $(sed -n '2,$p' "$WORK/fixture.err" 2>/dev/null)$(grep '^#' "$WORK/fixture.err")"
SHOT_HASH="sha256:$(sha256sum "$SHOT" 2>/dev/null | cut -d' ' -f1)"
GJSON="$WORK/grounding.json"
python3 "$VG" --image "$SHOT" --engine fixture-tsv --fixture-tsv "$FIX" \
  --snapshot-id cage-toy --snapshot-hash "$SHOT_HASH" \
  --hint-text CLICK_TARGET --hint-role button >"$GJSON" 2>"$WORK/vg.err" || {
    echo "FAIL: vision_grounding_ocr error"; cat "$WORK/vg.err"; cat "$GJSON" 2>/dev/null; exit 3; }

read -r GX GY GLABEL GCONF < <(python3 -c "
import json,sys
r=json.load(open('$GJSON'))
cands=r.get('candidates',[])
# prefer hint-matched, else exact label, else first
m=[c for c in cands if c.get('evidence',{}).get('matched_hint')] or \
  [c for c in cands if c.get('label')=='CLICK_TARGET'] or cands
if not m: print('NONE NONE NONE NONE'); sys.exit(0)
c=m[0]; print(c['center']['x'], c['center']['y'], c['label'], c['confidence'])
")
echo "== grounding result: schema=$(python3 -c "import json;print(json.load(open('$GJSON')).get('schema'))") candidates=$(python3 -c "import json;print(len(json.load(open('$GJSON')).get('candidates',[])))")"
echo "   selected: label=$GLABEL center=($GX,$GY) confidence=$GCONF  (derived, NOT hardcoded)"
[ "$GX" = "NONE" ] && { echo "FAIL: no grounding candidate selected"; exit 3; }

fmt='import sys,json;r=json.load(sys.stdin);print("     allowed=%s rc=%s detail=%s"%(r["allowed"],r.get("rc"),(r.get("detail") or "").replace(chr(10)," ")[:64]))'
echo "== inject via desktop_action.py (sway-ipc ISOLATED backend) at GROUNDED ($GX,$GY), target=$disp"
echo "   moveto $GX $GY:"; python3 "$DA" moveto "$GX" "$GY" --display "$disp" --swaysock "$SWAYSOCK" 2>&1 | python3 -c "$fmt" 2>&1
echo "   click left:";     python3 "$DA" click left        --display "$disp" --swaysock "$SWAYSOCK" 2>&1 | python3 -c "$fmt" 2>&1
sleep 0.6

echo "== toy AFTER:"; cat "$STATE" 2>/dev/null; echo
grim "$WORK/shot_after.png" 2>/dev/null && echo "   grim after: $(stat -c%s "$WORK/shot_after.png")B"

python3 -c "
import json
d=json.load(open('$STATE'))
gx,gy=$GX,$GY
if d.get('phase')=='clicked':
    print('== VERDICT:', 'HIT (grounding-derived click landed on control)' if d['in_button'] else 'MISS')
    print('   grounded_target=(%d,%d) click=%s button_center=%s dist=%.1fpx in_button=%s'%(
        gx,gy,tuple(d['click']),tuple(d['target_center']),d['dist_to_center'],d['in_button']))
    print('   note: dist>0 is the OCR ink-center vs geometric-center offset; HIT = clicked the right control')
    raise SystemExit(0 if d['in_button'] else 1)
print('== VERDICT: NO CLICK REGISTERED (phase=%s)'%d.get('phase')); raise SystemExit(1)
" 2>&1
