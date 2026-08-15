#!/usr/bin/env bash
# Cage AT-SPI INVOKE acceptance (Linux Computer Use, forum thread 79) — isolated.
#
# Proves desktop_invoke activates a real Gtk.Button via AT-SPI Action.do_action
# with ZERO coordinates (no screenshot, no OCR), and that its gate matches
# desktop_action's posture using a PID-subtree isolation primitive:
#   A. isolated invoke (--cage-pid = nested sway) -> ALLOWED, button activates.
#   B. --dry-run                                  -> ALLOWED, NO activation.
#   C. no --cage-pid, no --confirm (host posture) -> DENIED,  NO activation.
#
# AT-SPI is a session-global D-Bus registry, so desktop_invoke runs in the HOST
# env (display-independent) and isolates by process: the toy is exec'd by the
# nested sway, so its app PID is a descendant of $SWAY_PID.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INV="$DIR/../desktop_invoke.py"
SNAP="$DIR/../desktop_snapshot.py"
VERIFY="$DIR/../desktop_verify.py"
TOY="$DIR/toy_button.py"
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
# defense-in-depth: refuse if the nested sway somehow bound a physical output
out_names=$(swaymsg -t get_outputs 2>/dev/null | python3 -c "import sys,json;print(','.join(o['name'] for o in json.load(sys.stdin)))" 2>/dev/null)
case "$out_names" in *DP-*|*HDMI-*) echo "[ABORT] bound to host output '$out_names'"; exit 2 ;; esac
echo "== nested sway pid=$SWAY_PID disp=$disp outputs=${out_names:-?}"
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

echo "== VERDICT =="
python3 - "$S_present" "$A_allowed" "$A_rc" "$A_iso" "$A_acts" "$V_verdict" "$V_recover" "$B_allowed" "$B_acts" "$C_allowed" "$C_acts" <<'PY'
import sys
S_present,A_allowed,A_rc,A_iso,A_acts,V_verdict,V_recover,B_allowed,B_acts,C_allowed,C_acts = sys.argv[1:12]
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
]
for label, passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — L2 AT-SPI invoke isolated + gated (zero coordinates)" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
