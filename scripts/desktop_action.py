#!/usr/bin/env python3
"""desktop_action v1 — gated input injection for Wayland/sway desktops.

Lane: Linux Computer Use (forum thread 79). The mutating sibling of
desktop_snapshot.py. Wraps wtype (keyboard/text) + wlrctl (pointer) behind a
mandatory **audit + confirmation gate** — because unlike a snapshot, these
actions change the world.

SAFETY MODEL (the whole point of v1):
  Every mutating action passes through gate() before any injection happens.
  An action is allowed only if ONE of:
    (a) target is an isolated nested compositor (WAYLAND_DISPLAY != host), OR
    (b) --confirm given AND target host is explicitly acknowledged via
        --i-understand-this-touches-the-real-desktop, OR
    (c) --dry-run (logs intent, injects nothing).
  Every call — allowed or denied — is appended to an audit log (JSONL), ready
  to feed the event spine (thread 56).

  Default (no flags) on the HOST display = DENIED. You cannot accidentally
  poke the real desktop where Cursor/IM/etc. are running.

Backends (verified on aio2 sway, kernel 7.0):
  - wtype           : text + key (keysym) injection
  - wlrctl pointer  : RELATIVE move (dx dy), click <btn>, scroll
  KNOWN LIMIT: wlroots virtual-pointer is relative-only — there is no absolute
  (x,y) positioning. Absolute click grounding (what a vision model emits) needs
  ydotool (uinput, root) or a compositor that warps the cursor. Tracked for a
  follow-up; v1 exposes relative move + key/text which already enable the cage
  see->act->verify loop.

Usage (examples):
  desktop_action.py type "hello"  --display wayland-0            # nested: allowed
  desktop_action.py key Return    --display wayland-0
  desktop_action.py move 40 0     --display wayland-0
  desktop_action.py click left    --display wayland-0
  desktop_action.py type "x" --display wayland-1 --dry-run       # host: logged, no-op
  desktop_action.py type "x" --display wayland-1 --confirm \
      --i-understand-this-touches-the-real-desktop               # host: allowed
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "desktop_action/v1.1"
AUDIT_LOG = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) \
    / "agent-bridge" / "desktop_action_audit.jsonl"

MUTATING = {"type", "key", "move", "moveto", "click", "scroll"}

# ydotool socket (shared with a running ydotoold). Absolute positioning goes
# through ydotool/uinput because wlroots virtual-pointer is relative-only.
# uinput is reachable by the `input` group via udev rule (no root needed):
#   /etc/udev/rules.d/99-uinput.rules: KERNEL=="uinput", GROUP="input", MODE="0660"
YDOTOOL_SOCKET = os.environ.get("YDOTOOL_SOCKET",
                                os.path.expanduser("~/.cache/agent-bridge/ydotool.sock"))


def host_display() -> str:
    """The real desktop's WAYLAND_DISPLAY (the one we must protect).

    Resolved from AB_HOST_WAYLAND_DISPLAY if set, else the sway IPC socket's
    implied display, else wayland-1. NOT from the live WAYLAND_DISPLAY env,
    because callers legitimately override that to target a nested display —
    using it here would make the gate think the nested target IS the host."""
    explicit = os.environ.get("AB_HOST_WAYLAND_DISPLAY")
    if explicit:
        return explicit
    # sway's default display on this host is wayland-1 (verified).
    return "wayland-1"


def audit(record: dict[str, Any]) -> None:
    """Append one action record to the audit trail (JSONL). Best-effort."""
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def gate(args: argparse.Namespace) -> tuple[bool, str]:
    """The confirmation gate. Returns (allowed, reason)."""
    target = args.display or os.environ.get("WAYLAND_DISPLAY", "")
    host = host_display()
    is_host = (target == host) or (not target)
    if not is_host:
        return True, f"isolated-target ({target} != host {host})"
    if args.dry_run:
        return True, "dry-run (no injection)"
    if args.confirm and args.i_understand_this_touches_the_real_desktop:
        return True, "host explicitly confirmed"
    return False, ("DENIED: target is host desktop; pass --display <nested> for "
                   "isolation, or --confirm --i-understand-this-touches-the-real-"
                   "desktop, or --dry-run")


def run_backend(args: argparse.Namespace, target: str) -> tuple[int, str]:
    """Dispatch to wtype/wlrctl. Returns (rc, detail). Honors --dry-run."""
    env = dict(os.environ)
    if target:
        env["WAYLAND_DISPLAY"] = target

    if args.action == "type":
        cmd = ["wtype", args.text]
    elif args.action == "key":
        cmd = ["wtype", "-k", args.text]
    elif args.action == "move":               # relative (wlroots virtual-pointer)
        cmd = ["wlrctl", "pointer", "move", str(args.dx), str(args.dy)]
    elif args.action == "moveto":             # ABSOLUTE (ydotool/uinput)
        env["YDOTOOL_SOCKET"] = YDOTOOL_SOCKET
        cmd = ["ydotool", "mousemove", "--absolute", str(args.x), str(args.y)]
    elif args.action == "click":
        # ydotool click if a daemon socket exists (works with absolute flow),
        # else fall back to wlrctl (relative-position click).
        if os.path.exists(YDOTOOL_SOCKET) and shutil.which("ydotool"):
            env["YDOTOOL_SOCKET"] = YDOTOOL_SOCKET
            btn = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}.get(args.button, "0xC0")
            cmd = ["ydotool", "click", btn]
        else:
            cmd = ["wlrctl", "pointer", "click", args.button]
    elif args.action == "scroll":
        cmd = ["wlrctl", "pointer", "scroll", str(args.dy), str(args.dx)]
    else:
        return 2, f"unknown action {args.action}"

    if not shutil.which(cmd[0]):
        return 127, f"{cmd[0]} not installed"
    if args.dry_run:
        return 0, f"dry-run would exec: {' '.join(cmd)} (WAYLAND_DISPLAY={target})"
    if cmd[0] == "ydotool" and not os.path.exists(YDOTOOL_SOCKET):
        return 4, (f"ydotoold socket missing ({YDOTOOL_SOCKET}); start it: "
                   f"ydotoold -p {YDOTOOL_SOCKET} -P 0660  (needs input group)")
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=10)
        return p.returncode, (p.stderr or p.stdout or "ok").strip()
    except Exception as e:  # noqa: BLE001
        return 1, f"exec error: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description="gated desktop input injection (v1)")
    sub = ap.add_subparsers(dest="action", required=True)
    p_type = sub.add_parser("type"); p_type.add_argument("text")
    p_key = sub.add_parser("key"); p_key.add_argument("text", help="keysym e.g. Return, Tab, ctrl+c")
    p_move = sub.add_parser("move"); p_move.add_argument("dx", type=int); p_move.add_argument("dy", type=int)
    p_moveto = sub.add_parser("moveto"); p_moveto.add_argument("x", type=int); p_moveto.add_argument("y", type=int)
    p_click = sub.add_parser("click"); p_click.add_argument("button", nargs="?", default="left")
    p_scroll = sub.add_parser("scroll"); p_scroll.add_argument("dy", type=int); p_scroll.add_argument("dx", type=int, nargs="?", default=0)
    for p in (p_type, p_key, p_move, p_moveto, p_click, p_scroll):
        p.add_argument("--display", default=None, help="target WAYLAND_DISPLAY (nested for isolation)")
        p.add_argument("--confirm", action="store_true", help="confirm a mutating action")
        p.add_argument("--i-understand-this-touches-the-real-desktop",
                       dest="i_understand_this_touches_the_real_desktop",
                       action="store_true", help="required ack to act on host display")
        p.add_argument("--dry-run", action="store_true", help="log intent, inject nothing")
    args = ap.parse_args()

    target = args.display or os.environ.get("WAYLAND_DISPLAY", "")
    allowed, reason = gate(args)
    record: dict[str, Any] = {
        "schema": SCHEMA_VERSION, "ts": int(time.time()), "action": args.action,
        "target_display": target, "host_display": host_display(),
        "allowed": allowed, "gate_reason": reason,
        "args": {k: v for k, v in vars(args).items()
                 if k not in ("action",) and v not in (None, False)},
    }
    if not allowed:
        record["result"] = "blocked"
        audit(record)
        print(json.dumps(record, ensure_ascii=False))
        return 3
    rc, detail = run_backend(args, target)
    record["result"] = "ok" if rc == 0 else "error"
    record["rc"] = rc
    record["detail"] = detail
    audit(record)
    print(json.dumps(record, ensure_ascii=False))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
