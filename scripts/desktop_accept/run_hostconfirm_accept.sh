#!/usr/bin/env bash
# Host-confirm path (A) acceptance — two-phase pending/confirm machinery.
# (Linux Computer Use, forum thread 79; design: docs/design/HOST_CONFIRM_PATH.md)
#
# Exercises the full two-phase host-confirm flow WITHOUT touching the real desktop:
# a CAGE zenity is used as a stand-in "host" target by simply NOT passing --cage-pid,
# so the gate treats it as host. The app's native exit code is the unfakeable observable.
#
#   A. --request-host-confirm  -> pending token minted, NOTHING invoked (dialog stays up).
#   B. --confirm-token <tok>   -> executes -> zenity exits 0.
#   C. --confirm-token <tok>   -> same token again: DENIED (single-use).
#   D. ttl=1 + sleep 2         -> --confirm-token: DENIED (expired), dialog untouched.
#   E. plain host invoke (no --request-host-confirm, no --cage-pid) -> DENIED rc=3 (default closed).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INV="$DIR/../desktop_invoke.py"
WORK="$(mktemp -d)"; LOG="$WORK/sway.log"; CONF="$WORK/sway.conf"
SWAY_PID=""
cleanup() { [ -n "$SWAY_PID" ] && kill "$SWAY_PID" 2>/dev/null; wait "$SWAY_PID" 2>/dev/null; pkill -g 0 zenity 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT

cat >"$WORK/launch.sh" <<'LAUNCH'
#!/bin/sh
LC_ALL=C WAYLAND_DISPLAY="$2" zenity --question \
  --title=AB_HOSTCONFIRM --text="host-confirm cage proof" \
  --ok-label=INVOKEOK --cancel-label=INVOKECANCEL
echo $? > "$1"
LAUNCH
chmod +x "$WORK/launch.sh"

cat >"$CONF" <<EOF
default_border none
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
echo "== nested sway pid=$SWAY_PID disp=$disp =="

SEL=(--app zenity --role button --name INVOKEOK)
field() { python3 -c "import json,sys;print(json.load(sys.stdin).get('$1'))" 2>/dev/null; }
launch_zenity() { swaymsg exec "$WORK/launch.sh $1 $disp" >/dev/null 2>&1; sleep 2; }
kill_zenity() { pkill -f 'launch.sh' 2>/dev/null; pkill zenity 2>/dev/null; sleep 0.6; }

echo "== A. phase 1: --request-host-confirm mints token, invokes NOTHING =="
RES="$WORK/z1.exit"; rm -f "$RES"; launch_zenity "$RES"
P1=$(python3 "$INV" "${SEL[@]}" --request-host-confirm 2>&1); echo "   $P1"
A_pending=$(echo "$P1" | field pending); A_allowed=$(echo "$P1" | field allowed); TOKEN=$(echo "$P1" | field token)
sleep 1; A_exec="no"; [ -f "$RES" ] && A_exec="yes"
echo "   -> pending=$A_pending allowed=$A_allowed token=${TOKEN:0:8}… executed=$A_exec (must be: true/false/<tok>/no)"

echo "== B. phase 2: --confirm-token executes -> zenity exits 0 =="
P2=$(python3 "$INV" --confirm-token "$TOKEN" 2>&1); echo "   $P2"
B_allowed=$(echo "$P2" | field allowed); B_rc=$(echo "$P2" | field rc)
B_exit=""; for i in $(seq 1 25); do [ -f "$RES" ] && { B_exit=$(cat "$RES"); break; }; sleep 0.2; done
echo "   -> allowed=$B_allowed rc=$B_rc zenity_exit=${B_exit:-<none>} (must be: true/0/0)"

echo "== C. replay same token -> DENIED (single-use) =="
P3=$(python3 "$INV" --confirm-token "$TOKEN" 2>&1); echo "   $P3"
C_allowed=$(echo "$P3" | field allowed); C_rc=$(echo "$P3" | field rc)
echo "   -> allowed=$C_allowed rc=$C_rc (must be: false/3)"

echo "== D. ttl=1 + sleep 2 -> --confirm-token DENIED (expired), dialog untouched =="
kill_zenity; RES2="$WORK/z2.exit"; rm -f "$RES2"; launch_zenity "$RES2"
P4=$(python3 "$INV" "${SEL[@]}" --request-host-confirm --confirm-ttl 1 2>&1)
TOKEN2=$(echo "$P4" | field token); sleep 2
P5=$(python3 "$INV" --confirm-token "$TOKEN2" 2>&1); echo "   $P5"
D_allowed=$(echo "$P5" | field allowed); D_rc=$(echo "$P5" | field rc)
sleep 1; D_exec="no"; [ -f "$RES2" ] && D_exec="yes"
echo "   -> allowed=$D_allowed rc=$D_rc executed=$D_exec (must be: false/3/no)"

echo "== E. plain host invoke (no request-host-confirm, no cage-pid) -> DENIED rc=3 (default closed) =="
kill_zenity; RES3="$WORK/z3.exit"; rm -f "$RES3"; launch_zenity "$RES3"
P6=$(python3 "$INV" "${SEL[@]}" 2>&1); echo "   $P6"
E_allowed=$(echo "$P6" | field allowed); E_rc=$(echo "$P6" | field rc)
sleep 1; E_exec="no"; [ -f "$RES3" ] && E_exec="yes"
kill_zenity
echo "   -> allowed=$E_allowed rc=$E_rc executed=$E_exec (must be: false/3/no)"

echo "== VERDICT =="
python3 - "$A_pending" "$A_allowed" "$TOKEN" "$A_exec" "$B_allowed" "$B_rc" "$B_exit" \
            "$C_allowed" "$C_rc" "$D_allowed" "$D_rc" "$D_exec" "$E_allowed" "$E_rc" "$E_exec" <<'PY'
import sys
(A_pending,A_allowed,TOKEN,A_exec,B_allowed,B_rc,B_exit,
 C_allowed,C_rc,D_allowed,D_rc,D_exec,E_allowed,E_rc,E_exec) = sys.argv[1:16]
checks = [
  ("A phase1 pending==true",              A_pending=="True"),
  ("A phase1 allowed==false (not executed inline)", A_allowed=="False"),
  ("A phase1 token minted",               bool(TOKEN) and TOKEN not in ("None","")),
  ("A phase1 invoked NOTHING (dialog up)", A_exec=="no"),
  ("B phase2 allowed==true",              B_allowed=="True"),
  ("B phase2 rc==0",                      B_rc=="0"),
  ("B phase2 zenity exited 0 (OK activated)", B_exit=="0"),
  ("C replay DENIED (single-use)",        C_allowed=="False" and C_rc=="3"),
  ("D expired token DENIED",              D_allowed=="False" and D_rc=="3"),
  ("D expired path invoked NOTHING",      D_exec=="no"),
  ("E default host invoke DENIED rc==3",  E_allowed=="False" and E_rc=="3"),
  ("E default path invoked NOTHING",      E_exec=="no"),
]
ok=True
for label,passed in checks:
    print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("== RESULT:", "ALL PASS — two-phase host-confirm: pending/execute/single-use/expiry/default-closed" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
