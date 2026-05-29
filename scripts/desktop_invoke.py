#!/usr/bin/env python3
"""desktop_invoke — L2 semantic input for Linux Computer Use (forum thread 79).

Sibling of desktop_action.py. Where desktop_action drives the desktop by
*coordinates* (sway-ipc cursor / ydotool), desktop_invoke drives it by *meaning*:
it finds an AT-SPI accessible by app/role/name and calls its exposed
`Action.do_action` (e.g. a Gtk.Button's "click") — NO screenshot, NO OCR, NO
coordinates. This is the input-side dual of the bus-first read path
(desktop_snapshot already enumerates these accessibles).

SAFETY — same shape as desktop_action's confirmation gate, but the isolation
primitive differs. AT-SPI is a *session-global* D-Bus registry: a nested-cage
GTK app and a host app register on the SAME `org.a11y.Bus`, so isolation cannot
be by bus. Instead it is by PROCESS: an invoke is isolated iff the target
accessible's application PID is a descendant of a nested compositor (--cage-pid).
An action is allowed only if ONE of:
  (a) target app PID is a descendant of --cage-pid (isolated), OR
  (b) --confirm AND --i-understand-this-touches-the-real-desktop (host), OR
  (c) --dry-run (logs intent, invokes nothing).
Every call — allowed or denied — is appended to a JSONL audit trail. The MCP
wrapper never passes (b), so host invoke is structurally unreachable there.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "desktop_invoke/v0"
AUDIT_PATH = (
    Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    / "agent-bridge" / "desktop_invoke_audit.jsonl"
)
_ACTION_PRIORITY = ("click", "press", "activate", "do", "toggle")


def audit(record: dict[str, Any]) -> None:
    """Append one invoke record to the audit trail (JSONL). Best-effort."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def pid_is_descendant(pid: int, ancestor: int) -> bool:
    """True if `ancestor` appears on pid's PPID chain (or equals pid)."""
    if pid == ancestor:
        return True
    cur = pid
    for _ in range(64):
        try:
            with open(f"/proc/{cur}/stat", encoding="utf-8") as f:
                ppid = int(f.read().split()[3])
        except (OSError, ValueError, IndexError):
            return False
        if ppid <= 1:
            return False
        if ppid == ancestor:
            return True
        cur = ppid
    return False


def find_element(app_match, role_match, name_match, nth):
    """Search the AT-SPI desktop. Returns (element, app_name, app_pid) or (None, None, None)."""
    import pyatspi  # noqa: deferred so --help works without the binding

    matches: list[tuple[Any, str, int | None]] = []

    def walk(node, app_name, app_pid):
        try:
            role = node.getRoleName()
            name = node.name or ""
        except Exception:
            return
        ok_role = (not role_match) or (role_match.lower() in role.lower())
        ok_name = (not name_match) or (name_match.lower() in name.lower())
        if ok_role and ok_name and node.getRole() != pyatspi.ROLE_APPLICATION:
            matches.append((node, app_name, app_pid))
        for j in range(node.childCount):
            try:
                c = node.getChildAtIndex(j)
            except Exception:
                c = None
            if c is not None:
                walk(c, app_name, app_pid)

    desktop = pyatspi.Registry.getDesktop(0)
    for i in range(desktop.childCount):
        try:
            app = desktop.getChildAtIndex(i)
        except Exception:
            app = None
        if app is None:
            continue
        app_name = app.name or ""
        if app_match and app_match.lower() not in app_name.lower():
            continue
        try:
            app_pid = app.get_process_id()
        except Exception:
            app_pid = None
        walk(app, app_name, app_pid)

    if not matches:
        return None, None, None
    if nth >= len(matches):
        nth = 0
    return matches[nth]


def gate(isolated: bool, args: argparse.Namespace) -> tuple[bool, str]:
    if args.dry_run:
        return True, "dry-run: logged intent, invoked nothing"
    if isolated:
        return True, "isolated: target app PID is a descendant of --cage-pid"
    if args.confirm and getattr(args, "i_understand_this_touches_the_real_desktop", False):
        return True, "host-acknowledged via --confirm + --i-understand-this-touches-the-real-desktop"
    return False, ("DENIED: target app is not in the --cage-pid subtree (host or unknown); "
                   "pass --cage-pid <nested compositor pid> for isolation, or "
                   "--confirm --i-understand-this-touches-the-real-desktop, or --dry-run")


def do_invoke(element, want_action: str | None) -> tuple[int, str]:
    """Invoke the element's action. Returns (rc, detail). rc=0 on success."""
    try:
        action = element.queryAction()
    except Exception as exc:
        return 2, f"element exposes no Action interface: {exc}"
    names = [action.getName(k) for k in range(action.nActions)]
    if not names:
        return 2, "element exposes zero actions"
    idx = None
    if want_action:
        for k, n in enumerate(names):
            if n.lower() == want_action.lower():
                idx = k
                break
        if idx is None:
            return 2, f"requested action {want_action!r} not in {names}"
    else:
        for pref in _ACTION_PRIORITY:
            for k, n in enumerate(names):
                if n.lower() == pref:
                    idx = k
                    break
            if idx is not None:
                break
        if idx is None:
            idx = 0
    try:
        ok = action.doAction(idx)
    except Exception as exc:
        return 1, f"doAction({names[idx]!r}) raised: {exc}"
    return (0 if ok else 1), f"doAction({names[idx]!r}) -> {ok}; available={names}"


def main() -> int:
    ap = argparse.ArgumentParser(description="AT-SPI semantic invoke (L2 input, gated, isolated-only via MCP)")
    ap.add_argument("--app", default=None, help="application name substring (e.g. 'toy_button')")
    ap.add_argument("--role", default=None, help="role name substring (e.g. 'push button')")
    ap.add_argument("--name", default=None, help="accessible name/label substring (e.g. 'INVOKE_TARGET')")
    ap.add_argument("--nth", type=int, default=0, help="which match if several (default 0)")
    ap.add_argument("--action", default=None, help="action name to invoke (default: auto click/press/activate/first)")
    ap.add_argument("--cage-pid", type=int, default=(int(os.environ["AB_CAGE_PID"]) if os.environ.get("AB_CAGE_PID") else None),
                    help="nested compositor PID; target app must be its descendant for isolated invoke")
    ap.add_argument("--wait", type=float, default=4.0,
                    help="seconds to poll for the accessible to appear (a11y subtree can lag app registration)")
    ap.add_argument("--dry-run", action="store_true", help="log intent, invoke nothing")
    ap.add_argument("--confirm", action="store_true", help="confirm a host (non-isolated) invoke")
    ap.add_argument("--i-understand-this-touches-the-real-desktop",
                    dest="i_understand_this_touches_the_real_desktop", action="store_true",
                    help="explicit host acknowledgement (never passed by the MCP wrapper)")
    args = ap.parse_args()

    record: dict[str, Any] = {
        "schema": SCHEMA_VERSION, "ts": int(time.time()),
        "selector": {"app": args.app, "role": args.role, "name": args.name, "nth": args.nth},
        "action": args.action, "cage_pid": args.cage_pid, "dry_run": bool(args.dry_run),
    }

    if not (args.app or args.role or args.name):
        record.update(allowed=False, rc=2, error="no selector: pass at least one of --app/--role/--name")
        print(json.dumps(record, ensure_ascii=False))
        return 2

    element = app_name = app_pid = None
    deadline = time.time() + max(0.0, args.wait)
    try:
        while True:
            element, app_name, app_pid = find_element(args.app, args.role, args.name, args.nth)
            if element is not None or time.time() >= deadline:
                break
            time.sleep(0.4)
    except ImportError as exc:
        record.update(allowed=False, rc=2, error=f"pyatspi unavailable: {exc}")
        audit(record); print(json.dumps(record, ensure_ascii=False)); return 2

    if element is None:
        record.update(allowed=False, rc=2, error="no matching accessible found in AT-SPI registry")
        audit(record); print(json.dumps(record, ensure_ascii=False)); return 2

    isolated = bool(args.cage_pid and app_pid and pid_is_descendant(app_pid, args.cage_pid))
    record["found"] = {"app": app_name, "app_pid": app_pid, "isolated": isolated}

    allowed, reason = gate(isolated, args)
    record.update(allowed=allowed, gate_reason=reason)

    if not allowed:
        record["rc"] = 3
        audit(record); print(json.dumps(record, ensure_ascii=False)); return 3
    if args.dry_run:
        record["rc"] = 0
        audit(record); print(json.dumps(record, ensure_ascii=False)); return 0

    rc, detail = do_invoke(element, args.action)
    record["rc"] = rc
    record["detail"] = detail
    audit(record); print(json.dumps(record, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
