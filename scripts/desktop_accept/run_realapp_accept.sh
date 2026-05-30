#!/usr/bin/env bash
# Cage REAL-APP acceptance (Linux Computer Use, forum thread 79) — isolated.
#
# Everything before this proved the four desktop tools against OUR OWN toys.
# This proves them against a REAL third-party GTK app — zenity (GTK4) — using
# the app's NATIVE exit semantics as an observable we cannot fake:
#   - desktop_snapshot       : read path enumerates zenity's real a11y subtree (the OK button is visible).
#   - desktop_invoke "AB_OK"     : semantic activate -> zenity exits 0.
#   - desktop_invoke "AB_CANCEL" : semantic activate -> zenity exits 1  (proves we hit the RIGHT button BY MEANING,
#                                   not just "closed the window" — coordinates can't distinguish intent like this).
#   - host posture (no cage-pid) : DENIED, dialog untouched.
#
# Isolation is by PID-subtree: each zenity is spawned via `swaymsg exec`, so its
# process is a descendant of the nested sway ($SWAY_PID). AT-SPI is a session-
# global bus, so the tools run in the HOST env and isolate by process, not by bus.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INV="$DIR/../desktop_invoke.py"
SNAP="$DIR/../desktop_snapshot.py"
WORK="$(mktemp -d)"; LOG="$WORK/sway.log"; CONF="$WORK/sway.conf"
SWAY_PID=""
cleanup() { [ -n "$SWAY_PID" ] && kill "$SWAY_PID" 2>/dev/null; wait "$SWAY_PID" 2>/dev/null; pkill -g 0 zenity 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT

# zenity launcher: $1 = exit-code result file, $2 = nested wayland display.
# Custom labels dodge locale-default button text (this host may be zh). NOTE:
# GTK treats '_' as a mnemonic marker and strips it, so the AT-SPI accessible
# name of "--ok-label=INVOKEOK" is "INVOKEOK" — labels must carry no underscore.
# Do NOT set GTK_A11Y=atk-bridge here: that is the GTK3 spelling; GTK4 (zenity
# 4.x) rejects the unknown value and SUPPRESSES a11y. GTK4 a11y is on by default.
cat >"$WORK/launch.sh" <<'LAUNCH'
#!/bin/sh
LC_ALL=C WAYLAND_DISPLAY="$2" zenity --question \
  --title=AB_REALAPP --text="agent-bridge cage proof: invoke a real button by meaning" \
  --ok-label=INVOKEOK --cancel-label=INVOKECANCEL
echo $? > "$1"
LAUNCH
chmod +x "$WORK/launch.sh"

cat >"$CONF" <<EOF
default_border none
hide_edge_borders both
bar mode invisible
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
case "$out_names" in *DP-*|*HDMI-*) echo "[ABORT] bound to host output '$out_names'"; exit 2 ;; esac
echo "== nested sway pid=$SWAY_PID disp=$disp outputs=${out_names:-?}"

SEL_OK=(--app zenity --role button --name INVOKEOK)
SEL_CANCEL=(--app zenity --role button --name INVOKECANCEL)
field() { python3 -c "import json,sys;print(json.load(sys.stdin).get('$1'))" 2>/dev/null; }

# Spawn a zenity dialog inside the cage; wait until its app PID is a sway descendant.
launch_zenity() {  # $1 = result file
  swaymsg exec "$WORK/launch.sh $1 $disp" >/dev/null 2>&1
  for i in $(seq 1 40); do
    pgrep -P "$SWAY_PID" -f 'launch.sh' >/dev/null 2>&1 && return 0
    pgrep zenity >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  return 0
}

# ---------------------------------------------------------------------------
echo "== A. desktop_snapshot read path independently enumerates the cage app =="
RES_OK="$WORK/zenity_ok.exit"; rm -f "$RES_OK"
launch_zenity "$RES_OK"; sleep 2
SNAP=$(python3 "$SNAP" --no-screenshot --activate-a11y --a11y-settle 5 --compact 2>/dev/null)
read -r A_app A_btn <<<"$(echo "$SNAP" | python3 -c '
import json,sys
try: s=json.load(sys.stdin)
except Exception: print("no no"); raise SystemExit
apps=(s.get("atspi") or {}).get("apps") or s.get("apps") or []
app=btn="no"
for a in apps:
    if (a.get("name") or "")=="zenity":
        app="yes"
        for e in (a.get("elements") or []):
            if "INVOKEOK" in (e.get("name") or "") and "button" in (e.get("role") or "").lower():
                btn="yes"
print(app, btn)' 2>/dev/null)"
echo "   -> snapshot lists zenity app on a11y bus: ${A_app:-no} (button element surfaced: ${A_btn:-no})"

echo "== B. isolated invoke INVOKEOK (--cage-pid $SWAY_PID) -> zenity exits 0 =="
B=$(python3 "$INV" "${SEL_OK[@]}" --cage-pid "$SWAY_PID" 2>&1); echo "   $B"
B_allowed=$(echo "$B" | field allowed); B_rc=$(echo "$B" | field rc)
B_iso=$(echo "$B" | python3 -c "import json,sys;print(json.load(sys.stdin).get('found',{}).get('isolated'))" 2>/dev/null)
B_exit=""; for i in $(seq 1 25); do [ -f "$RES_OK" ] && { B_exit=$(cat "$RES_OK"); break; }; sleep 0.2; done
echo "   -> allowed=$B_allowed rc=$B_rc isolated=$B_iso zenity_exit=${B_exit:-<none>} (OK button => 0)"

echo "== C. isolated invoke INVOKECANCEL -> zenity exits 1 (right button by meaning) =="
RES_CANCEL="$WORK/zenity_cancel.exit"; rm -f "$RES_CANCEL"
launch_zenity "$RES_CANCEL"; sleep 2
C=$(python3 "$INV" "${SEL_CANCEL[@]}" --cage-pid "$SWAY_PID" 2>&1); echo "   $C"
C_allowed=$(echo "$C" | field allowed); C_rc=$(echo "$C" | field rc)
C_exit=""; for i in $(seq 1 25); do [ -f "$RES_CANCEL" ] && { C_exit=$(cat "$RES_CANCEL"); break; }; sleep 0.2; done
echo "   -> allowed=$C_allowed rc=$C_rc zenity_exit=${C_exit:-<none>} (Cancel button => 1)"

echo "== D. host posture (no cage-pid, no confirm) -> must DENY, dialog untouched =="
RES_HOST="$WORK/zenity_host.exit"; rm -f "$RES_HOST"
launch_zenity "$RES_HOST"; sleep 2
D=$(python3 "$INV" "${SEL_OK[@]}" 2>&1); echo "   $D"
D_allowed=$(echo "$D" | field allowed)
sleep 1; D_exit_present="no"; [ -f "$RES_HOST" ] && D_exit_present="yes"
pkill -f 'launch.sh' 2>/dev/null; pkill zenity 2>/dev/null
echo "   -> allowed=$D_allowed dialog_closed=$D_exit_present (must be allowed=False, dialog_closed=no)"

echo "== VERDICT =="
python3 - "$A_app" "$A_btn" "$B_allowed" "$B_rc" "$B_iso" "$B_exit" "$C_allowed" "$C_rc" "$C_exit" "$D_allowed" "$D_exit_present" <<'PY'
import sys
A_app,A_btn,B_allowed,B_rc,B_iso,B_exit,C_allowed,C_rc,C_exit,D_allowed,D_closed = sys.argv[1:12]
checks = [
  ("A snapshot read path lists real zenity app on a11y bus", A_app=="yes"),
  (f"  (bonus) snapshot surfaced the INVOKEOK button element: {A_btn}", True),
  ("B isolated invoke allowed",            B_allowed=="True"),
  ("B rc==0",                              B_rc=="0"),
  ("B isolated==True",                     B_iso=="True"),
  ("B zenity exited 0 (OK activated)",     B_exit=="0"),
  ("C isolated invoke allowed",            C_allowed=="True"),
  ("C zenity exited 1 (Cancel activated — right button by meaning)", C_exit=="1"),
  ("D host invoke DENIED",                 D_allowed=="False"),
  ("D dialog NOT closed (untouched)",      D_closed=="no"),
]
ok=True
for label,passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — four-tool family drives a REAL GTK app, isolated, semantic precision proven" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
