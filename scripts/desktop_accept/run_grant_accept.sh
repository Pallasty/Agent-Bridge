#!/usr/bin/env bash
# Pre-authorized capability grants (host-confirm path C) — acceptance.
# (Linux Computer Use, thread 79; design docs/design/HOST_CONFIRM_PATH.md §C)
#
# A human-minted grant lets a covered host action run WITHOUT a per-action confirm,
# bounded by ttl + max_uses + scope + revoke. Cage click on the toy target is the
# observable; the cage is treated as host via AB_HOST_WAYLAND_DISPLAY.
#
#   A. --use-grant with NO grant            -> DENIED (clicks 0).
#   B. mint action/click grant (max-uses 2) -> --use-grant runs -> clicks 1.
#   C. --use-grant again                     -> clicks 2 (2nd of 2 uses).
#   D. --use-grant again                     -> DENIED (max_uses exhausted), clicks 2.
#   E. fresh action/click grant, ttl 1, sleep 2 -> --use-grant DENIED (expired), clicks 2.
#   F. mint + revoke a grant                 -> --use-grant DENIED (revoked), clicks 2.
#   G. grant scoped to action=type           -> click --use-grant DENIED (scope), clicks 2.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DA="$DIR/../desktop_action.py"
GRANT="$DIR/../desktop_grant.py"
TOY="$DIR/toy_target.py"
STATE="$HOME/.cache/agent-bridge/cage_toy_hit.json"
GRANTS_DIR="$HOME/.cache/agent-bridge/desktop_grants"
WORK="$(mktemp -d)"; LOG="$WORK/sway.log"; CONF="$WORK/sway.conf"
SWAY_PID=""
cleanup() { [ -n "$SWAY_PID" ] && kill "$SWAY_PID" 2>/dev/null; wait "$SWAY_PID" 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT
rm -f "$STATE"; rm -rf "$GRANTS_DIR"   # clean slate: no leftover grants

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
echo "== nested sway pid=$SWAY_PID disp=$disp =="
sleep 2

field() { python3 -c "import json,sys;print(json.load(sys.stdin).get('$1'))" 2>/dev/null; }
clicks() { python3 -c "import json;print(json.load(open('$STATE')).get('clicks',-1))" 2>/dev/null; }
DAC=(click left --display "$disp" --swaysock "$SWAYSOCK" --use-grant)
# wl_pointer events are async; settle before reading the toy's click counter.
run_ug() { local o; o=$(python3 "$DA" "${DAC[@]}" 2>&1); sleep 0.7; printf '%s' "$o"; }

# pre-position the cage cursor over the toy button (isolated moveto)
python3 "$DA" moveto 670 410 --display "$disp" --swaysock "$SWAYSOCK" >/dev/null 2>&1
export AB_HOST_WAYLAND_DISPLAY="$disp"

echo "== A. --use-grant with NO grant -> DENIED =="
A=$(run_ug); echo "   $A"
A_allowed=$(echo "$A" | field allowed); A_clicks=$(clicks)
echo "   -> allowed=$A_allowed clicks=$A_clicks (must false/0)"

echo "== B. mint action/click grant (max-uses 2); --use-grant runs =="
GID=$(python3 "$GRANT" grant --kind action --action click --ttl 60 --max-uses 2 --note accept | field grant_id)
echo "   grant=$GID"
B=$(run_ug); echo "   $B"
B_allowed=$(echo "$B" | field allowed); B_grant=$(echo "$B" | field grant_id); B_clicks=$(clicks)
echo "   -> allowed=$B_allowed grant_id=$B_grant clicks=$B_clicks (must true/<gid>/1)"

echo "== C. --use-grant again (2nd of 2) =="
C=$(run_ug)
C_allowed=$(echo "$C" | field allowed); C_clicks=$(clicks)
echo "   -> allowed=$C_allowed clicks=$C_clicks (must true/2)"

echo "== D. --use-grant again -> DENIED (max_uses exhausted) =="
D=$(run_ug); echo "   $D"
D_allowed=$(echo "$D" | field allowed); D_clicks=$(clicks)
echo "   -> allowed=$D_allowed clicks=$D_clicks (must false/2)"

echo "== E. fresh grant ttl=1 + sleep 2 -> DENIED (expired) =="
python3 "$GRANT" grant --kind action --action click --ttl 1 --note exp >/dev/null
sleep 2
E=$(run_ug)
E_allowed=$(echo "$E" | field allowed); E_clicks=$(clicks)
echo "   -> allowed=$E_allowed clicks=$E_clicks (must false/2)"

echo "== F. mint + revoke -> DENIED (revoked) =="
RID=$(python3 "$GRANT" grant --kind action --action click --ttl 60 --note rev | field grant_id)
python3 "$GRANT" revoke "$RID" >/dev/null
F=$(run_ug)
F_allowed=$(echo "$F" | field allowed); F_clicks=$(clicks)
echo "   -> allowed=$F_allowed clicks=$F_clicks (must false/2)"

echo "== G. grant scoped to action=type -> click --use-grant DENIED (scope) =="
python3 "$GRANT" grant --kind action --action type --ttl 60 --note scope >/dev/null
G=$(run_ug)
G_allowed=$(echo "$G" | field allowed); G_clicks=$(clicks)
echo "   -> allowed=$G_allowed clicks=$G_clicks (must false/2)"

rm -rf "$GRANTS_DIR"   # clean up grants we minted
echo "== VERDICT =="
python3 - "$A_allowed" "$A_clicks" "$B_allowed" "$B_grant" "$B_clicks" "$C_allowed" "$C_clicks" \
            "$D_allowed" "$D_clicks" "$E_allowed" "$E_clicks" "$F_allowed" "$F_clicks" "$G_allowed" "$G_clicks" <<'PY'
import sys
(A_allowed,A_clicks,B_allowed,B_grant,B_clicks,C_allowed,C_clicks,
 D_allowed,D_clicks,E_allowed,E_clicks,F_allowed,F_clicks,G_allowed,G_clicks) = sys.argv[1:16]
checks = [
  ("A no grant -> DENIED, nothing injected",   A_allowed=="False" and A_clicks=="0"),
  ("B grant covers -> ran (clicks 1)",         B_allowed=="True" and B_clicks=="1"),
  ("B records grant_id",                       bool(B_grant) and B_grant not in ("None","")),
  ("C 2nd use ran (clicks 2)",                 C_allowed=="True" and C_clicks=="2"),
  ("D max_uses exhausted -> DENIED (clicks 2)", D_allowed=="False" and D_clicks=="2"),
  ("E expired grant -> DENIED (clicks 2)",     E_allowed=="False" and E_clicks=="2"),
  ("F revoked grant -> DENIED (clicks 2)",     F_allowed=="False" and F_clicks=="2"),
  ("G scope mismatch (type!=click) -> DENIED (clicks 2)", G_allowed=="False" and G_clicks=="2"),
]
ok=True
for label,passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — capability grants: cover/deny/max-uses/expiry/revoke/scope" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
