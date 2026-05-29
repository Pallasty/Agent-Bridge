#!/usr/bin/env python3
"""desktop_snapshot v0 — read-only structured snapshot of a Wayland/sway desktop.

Lane: Linux Computer Use (forum thread 79). This is the v0 PoC backend behind a
future `desktop_snapshot` MCP tool — the desktop sibling of browser_snapshot /
mobile_ui_snapshot. It answers "what is on screen right now, structurally" with
zero mutating actions and zero extra privilege.

Design (bus-first, vision-as-grounding — per forum #1634/#1637):

  source            role                       reliability (aio2-verified)
  ----------------  -------------------------  ---------------------------------
  swaymsg outputs   multi-monitor geometry     universal (wlroots IPC)
  swaymsg tree      window skeleton            universal: every window exposes
                                               app_id/class/pid/geom/focus/title
  grim              pixels + screenshot meta   per-output PNG (optional)
  AT-SPI (pyatspi)  in-window semantic elems   PARTIAL: GTK apps expose a tree;
                                               Electron/Qt/terminals/private apps
                                               do NOT -> marked a11y:unavailable,
                                               fallback=vision

Priority ladder for grounding (verified on aio2 sway, kernel 7.0 / Ubuntu 26.04):
  shell/CDP > swaymsg window-IPC (universal) > AT-SPI (GTK only) > vision/OCR

v0 scope: read-only aggregation only. NO input injection, NO mutating actions
(those are v1, behind an audit/confirmation gate). Output is plain JSON so it can
feed the event spine (thread 56) or a Claude-native computer-use tool contract.

Usage:
  desktop_snapshot.py                      # full snapshot JSON to stdout
  desktop_snapshot.py --no-screenshot      # skip grim (faster, no PNG written)
  desktop_snapshot.py --no-atspi           # skip AT-SPI element extraction
  desktop_snapshot.py --screenshot-dir DIR # where grim writes PNGs (default: tmp)
  desktop_snapshot.py --max-elements N     # cap AT-SPI elements per app (default 200)
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

SCHEMA_VERSION = "desktop_snapshot/v0.5"

# AT-SPI sentinel for "not mapped / offscreen / no valid extents". pyatspi
# returns INT_MIN here; treat as offscreen, never as a real coordinate.
ATSPI_OFFSCREEN = -2147483648

# org.a11y.Status.IsEnabled is a global switch: many toolkits (Qt, Electron)
# only build their accessibility tree when an AT client flips it true. GTK apps
# expose a tree regardless. v0.5 verified: flipping it true makes Qt(Strawberry)
# appear live; Electron(Cursor) still needs --force-renderer-accessibility at
# launch. We only touch it when --activate-a11y is given, and restore it after.
A11Y_STATUS_DEST = "org.a11y.Bus"
A11Y_STATUS_PATH = "/org/a11y/bus"
A11Y_STATUS_IFACE = "org.a11y.Status"

# Roles worth surfacing as actionable/interesting from an AT-SPI tree. Kept small
# on purpose — v0 is a probe, not a full accessibility crawler.
INTERESTING_ATSPI_ROLES = {
    "push button", "toggle button", "radio button", "check box", "menu item",
    "menu", "text", "entry", "password text", "combo box", "list item",
    "tab", "page tab", "link", "slider", "spin button", "label", "heading",
    "table cell", "tree item",
}


def _run(cmd: list[str], timeout: float = 8.0,
         env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a command, return (rc, stdout, stderr). Never raises on non-zero."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout: {' '.join(cmd)}"


def _sway_env() -> dict[str, str]:
    """Resolve SWAYSOCK (sway IPC socket) — env first, then probe runtime dir."""
    env = dict(os.environ)
    if env.get("SWAYSOCK") and Path(env["SWAYSOCK"]).exists():
        return env
    uid = os.getuid()
    runtime = env.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    for p in sorted(Path(runtime).glob("sway-ipc.*.sock")):
        env["SWAYSOCK"] = str(p)
        break
    return env


def _swaymsg(kind: str, env: dict[str, str]) -> Any:
    """swaymsg -t <kind> -r -> parsed JSON, or {'error': ...}."""
    if not shutil.which("swaymsg"):
        return {"error": "swaymsg not installed"}
    rc, out, err = _run(["swaymsg", "-t", kind, "-r"], timeout=6.0, env=env)
    if rc != 0:
        return {"error": f"swaymsg -t {kind} rc={rc}: {err.strip()}"}
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        return {"error": f"json decode: {e}"}


def collect_outputs(env: dict[str, str]) -> list[dict[str, Any]]:
    """Active displays with geometry — the coordinate space windows live in."""
    data = _swaymsg("get_outputs", env)
    if isinstance(data, dict) and "error" in data:
        return [{"error": data["error"]}]
    outs = []
    for o in data:
        rect = o.get("rect", {})
        mode = o.get("current_mode", {}) or {}
        outs.append({
            "name": o.get("name"),
            "active": o.get("active"),
            "focused": o.get("focused"),
            "rect": {"x": rect.get("x"), "y": rect.get("y"),
                     "width": rect.get("width"), "height": rect.get("height")},
            "mode": {"width": mode.get("width"), "height": mode.get("height"),
                     "refresh": mode.get("refresh")},
            "scale": o.get("scale"),
        })
    return outs


def _walk_tree(node: dict[str, Any], windows: list[dict[str, Any]]) -> None:
    """Depth-first collect real toplevel windows from a sway tree node."""
    ntype = node.get("type")
    wp = node.get("window_properties") or {}
    app_id = node.get("app_id")
    is_window = ntype in ("con", "floating_con") and (app_id or wp.get("class")) \
        and node.get("pid") is not None
    if is_window:
        r = node.get("rect", {})
        windows.append({
            "id": node.get("id"),
            "app_id": app_id,                       # native Wayland id
            "x11_class": wp.get("class"),           # XWayland fallback
            "x11_instance": wp.get("instance"),
            "pid": node.get("pid"),
            "name": node.get("name"),               # window title
            "focused": node.get("focused", False),
            "visible": node.get("visible"),
            "floating": ntype == "floating_con",
            "rect": {"x": r.get("x"), "y": r.get("y"),
                     "width": r.get("width"), "height": r.get("height")},
            "output": node.get("output"),
        })
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        _walk_tree(child, windows)


def collect_windows(env: dict[str, Any]) -> list[dict[str, Any]]:
    """Universal window skeleton via swaymsg get_tree (works for ALL apps)."""
    tree = _swaymsg("get_tree", env)
    if isinstance(tree, dict) and "error" in tree:
        return [{"error": tree["error"]}]
    windows: list[dict[str, Any]] = []
    _walk_tree(tree, windows)
    return windows


def collect_screenshots(outputs: list[dict[str, Any]], screenshot_dir: Path,
                        env: dict[str, str]) -> list[dict[str, Any]]:
    """Per-output PNG via grim. Optional; returns metadata (path + size)."""
    if not shutil.which("grim"):
        return [{"error": "grim not installed"}]
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    shots = []
    for o in outputs:
        name = o.get("name")
        if not name or not o.get("active"):
            continue
        path = screenshot_dir / f"snap_{name}_{ts}.png"
        rc, _, err = _run(["grim", "-o", name, str(path)], timeout=15.0,
                          env=env)
        entry = {"output": name, "path": str(path) if rc == 0 else None}
        if rc == 0:
            entry["bytes"] = path.stat().st_size if path.exists() else None
            entry["width"] = o.get("mode", {}).get("width")
            entry["height"] = o.get("mode", {}).get("height")
        else:
            entry["error"] = f"grim rc={rc}: {err.strip()}"
        shots.append(entry)
    return shots


def _a11y_get_enabled() -> bool | None:
    """Read org.a11y.Status.IsEnabled. None if unreadable."""
    rc, out, _ = _run(["gdbus", "call", "--session", "--dest", A11Y_STATUS_DEST,
                       "--object-path", A11Y_STATUS_PATH, "--method",
                       "org.freedesktop.DBus.Properties.Get",
                       A11Y_STATUS_IFACE, "IsEnabled"], timeout=5.0)
    if rc != 0:
        return None
    return "true" in out.lower()


def _a11y_set_enabled(value: bool) -> bool:
    """Set org.a11y.Status.IsEnabled. Returns True on success."""
    rc, _, _ = _run(["gdbus", "call", "--session", "--dest", A11Y_STATUS_DEST,
                    "--object-path", A11Y_STATUS_PATH, "--method",
                    "org.freedesktop.DBus.Properties.Set", A11Y_STATUS_IFACE,
                    "IsEnabled", f"<{'true' if value else 'false'}>"], timeout=5.0)
    return rc == 0


def collect_atspi(max_elements: int, windows: list[dict[str, Any]],
                  per_app_budget: float = 4.0) -> dict[str, Any]:
    """In-window semantic elements via AT-SPI. PARTIAL coverage by design:
    GTK apps expose a tree regardless; Qt/Electron need the global a11y switch
    (and Electron also --force-renderer-accessibility). v0.5 adds:
      - INT_MIN sentinel -> offscreen (never a real coord)
      - local->global coordinate normalization via pid-matched window rect
      - per-app wall-clock budget (some Qt trees stall the traversal)."""
    try:
        import pyatspi  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"pyatspi import failed: {e}",
                "apps": []}

    # pid -> window rect (for local->global offset). A pid may own several
    # windows; we keep the focused/first as the offset anchor (v0.5 heuristic).
    pid_rect: dict[int, dict[str, Any]] = {}
    for w in windows:
        if "error" in w or w.get("pid") is None:
            continue
        pid_rect.setdefault(w["pid"], w["rect"])

    apps_out: list[dict[str, Any]] = []
    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"getDesktop failed: {e}", "apps": []}

    def app_pid(app) -> int | None:
        try:
            return int(app.get_process_id())
        except Exception:  # noqa: BLE001
            return None

    for i in range(desktop.childCount):
        try:
            app = desktop.getChildAtIndex(i)
        except Exception:  # noqa: BLE001
            continue
        if app is None:
            continue
        elements: list[dict[str, Any]] = []
        counter = {"n": 0}
        deadline = time.time() + per_app_budget
        timed_out = {"v": False}
        pid = app_pid(app)
        anchor = pid_rect.get(pid) if pid is not None else None

        def visit(acc, depth: int) -> None:
            if acc is None or counter["n"] >= max_elements or depth > 25:
                return
            if time.time() > deadline:
                timed_out["v"] = True
                return
            try:
                role = acc.getRoleName()
            except Exception:  # noqa: BLE001
                role = None
            if role in INTERESTING_ATSPI_ROLES:
                bounds = None
                offscreen = False
                try:
                    comp = acc.queryComponent()
                    ext = comp.getExtents(pyatspi.DESKTOP_COORDS)
                    if ext.x <= ATSPI_OFFSCREEN or ext.y <= ATSPI_OFFSCREEN \
                            or ext.width <= 0 or ext.height <= 0:
                        offscreen = True
                    else:
                        gx, gy = ext.x, ext.y
                        # Some toolkits report window-local coords; if the value
                        # is too small to be on the (multi-monitor) global plane
                        # AND we have a window anchor, treat as local + offset.
                        norm = "global"
                        if anchor and ext.x < anchor.get("x", 0):
                            gx = ext.x + anchor.get("x", 0)
                            gy = ext.y + anchor.get("y", 0)
                            norm = "local+offset"
                        bounds = {"x": gx, "y": gy, "width": ext.width,
                                  "height": ext.height, "coord": norm}
                except Exception:  # noqa: BLE001
                    pass
                states = []
                try:
                    ss = acc.getState()
                    for st in (pyatspi.STATE_VISIBLE, pyatspi.STATE_SHOWING,
                               pyatspi.STATE_ENABLED, pyatspi.STATE_FOCUSED,
                               pyatspi.STATE_SENSITIVE):
                        if ss.contains(st):
                            states.append(pyatspi.stateToString(st))
                except Exception:  # noqa: BLE001
                    pass
                name = None
                try:
                    name = acc.name
                except Exception:  # noqa: BLE001
                    pass
                if not offscreen:  # only surface actionable (on-screen) elements
                    elements.append({"role": role, "name": name,
                                     "bounds": bounds, "states": states})
                    counter["n"] += 1
            try:
                for j in range(acc.childCount):
                    if time.time() > deadline:
                        timed_out["v"] = True
                        return
                    visit(acc.getChildAtIndex(j), depth + 1)
            except Exception:  # noqa: BLE001
                return

        try:
            app_name = app.name
            child_count = app.childCount
        except Exception:  # noqa: BLE001
            app_name, child_count = None, 0
        if child_count > 0:
            try:
                for j in range(child_count):
                    visit(app.getChildAtIndex(j), 0)
            except Exception:  # noqa: BLE001
                pass
        apps_out.append({
            "name": app_name,
            "pid": pid,
            "toplevel_count": child_count,
            "element_count": len(elements),
            "elements": elements,
            "timed_out": timed_out["v"],
            "coverage": "ok" if elements else
                        ("registered-empty" if child_count else "no-window"),
        })
    return {"available": True, "apps": apps_out}


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    env = _sway_env()
    t0 = time.time()
    outputs = collect_outputs(env)
    windows = collect_windows(env)
    snap: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "captured_at": int(t0),
        "session": {
            "type": env.get("XDG_SESSION_TYPE"),
            "wayland_display": env.get("WAYLAND_DISPLAY"),
            "swaysock": env.get("SWAYSOCK"),
            "compositor": "sway" if env.get("SWAYSOCK") else None,
        },
        "outputs": outputs,
        "windows": windows,
        "window_count": len([w for w in windows if "error" not in w]),
    }
    if not args.no_screenshot:
        sdir = Path(args.screenshot_dir) if args.screenshot_dir else \
            Path(env.get("XDG_RUNTIME_DIR", "/tmp")) / "desktop_snapshot"
        snap["screenshots"] = collect_screenshots(outputs, sdir, env)
    else:
        snap["screenshots"] = {"skipped": True}
    if not args.no_atspi:
        # Optionally flip the global a11y switch so Qt/Electron build their tree.
        # We restore the prior value afterwards (respect system state).
        a11y_meta: dict[str, Any] = {"activated": False}
        prior = None
        if args.activate_a11y:
            prior = _a11y_get_enabled()
            a11y_meta["prior_enabled"] = prior
            if prior is False and _a11y_set_enabled(True):
                a11y_meta["activated"] = True
                time.sleep(args.a11y_settle)  # let toolkits build their trees
        snap["atspi"] = collect_atspi(args.max_elements, windows,
                                      per_app_budget=args.atspi_budget)
        snap["atspi"]["activation"] = a11y_meta
        if a11y_meta.get("activated"):  # restore prior state
            _a11y_set_enabled(bool(prior))
        # Cross-reference by PID (robust) — which windows have a11y coverage.
        a11y_pids = {a.get("pid") for a in snap["atspi"].get("apps", [])
                     if a.get("coverage") == "ok" and a.get("pid")}
        for w in windows:
            if "error" in w:
                continue
            w["grounding"] = "atspi" if w.get("pid") in a11y_pids else "vision"
    else:
        snap["atspi"] = {"skipped": True}
    snap["elapsed_ms"] = int((time.time() - t0) * 1000)
    return snap


def main() -> int:
    ap = argparse.ArgumentParser(description="read-only Wayland/sway desktop snapshot (v0.5)")
    ap.add_argument("--no-screenshot", action="store_true", help="skip grim capture")
    ap.add_argument("--no-atspi", action="store_true", help="skip AT-SPI extraction")
    ap.add_argument("--screenshot-dir", default=None, help="dir for grim PNGs")
    ap.add_argument("--max-elements", type=int, default=200,
                    help="cap AT-SPI elements per app (default 200)")
    ap.add_argument("--atspi-budget", type=float, default=4.0,
                    help="per-app AT-SPI traversal budget seconds (default 4)")
    ap.add_argument("--activate-a11y", action="store_true",
                    help="flip global org.a11y.Status.IsEnabled true so Qt/Electron "
                         "build trees, then restore (Electron also needs launch flag)")
    ap.add_argument("--a11y-settle", type=float, default=5.0,
                    help="seconds to wait after activating a11y (default 5)")
    ap.add_argument("--compact", action="store_true", help="single-line JSON")
    args = ap.parse_args()
    snap = build_snapshot(args)
    json.dump(snap, sys.stdout, ensure_ascii=False,
              indent=None if args.compact else 2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
