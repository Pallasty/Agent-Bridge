#!/usr/bin/env python3
"""macOS AX read-only feasibility probe.

This probe is intentionally narrow: it checks whether the current process is
trusted for Accessibility, then, only when already trusted, asks System Events
for frontmost-application/window metadata. It never clicks, types, focuses,
activates apps, changes permissions, or calls AXIsProcessTrustedWithOptions
with a prompt flag.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import subprocess
import time
from typing import Any

SCHEMA_VERSION = "macos_ax_probe/v0"


def _ax_is_trusted() -> tuple[bool | None, str | None]:
    """Return AXIsProcessTrusted() without requesting permission."""
    if platform.system() != "Darwin":
        return None, None
    try:
        app_services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrusted()), None
    except Exception as exc:  # noqa: BLE001 - probe must degrade, not raise
        return None, f"AXIsProcessTrusted failed: {exc}"


def _frontmost_jxa(max_windows: int, timeout_secs: float) -> tuple[dict[str, Any] | None, str | None]:
    """Read frontmost app and windows via System Events/JXA."""
    jxa = f"""
function safe(fn) {{
  try {{
    const value = fn();
    if (value === undefined) return null;
    return value;
  }} catch (e) {{
    return null;
  }}
}}
const se = Application("System Events");
const procSpec = se.applicationProcesses.whose({{frontmost: true}});
const app = procSpec[0];
if (!app) {{
  JSON.stringify({{frontmost_app: null, window_count: 0, windows: []}});
}} else {{
  const wins = safe(() => app.windows()) || [];
  const count = safe(() => wins.length) || 0;
  const kept = [];
  const limit = Math.min(count, {max_windows});
  for (let i = 0; i < limit; i++) {{
    const w = wins[i];
    const position = safe(() => w.position());
    const size = safe(() => w.size());
    kept.push({{
      "index": i,
      "title": safe(() => w.name()),
      "role": safe(() => w.attributes.byName("AXRole").value()),
      "subrole": safe(() => w.attributes.byName("AXSubrole").value()),
      "focused": safe(() => w.attributes.byName("AXFocused").value()),
      "position": position,
      "size": size,
      "rect": (position && size) ? {{
        "x": position[0],
        "y": position[1],
        "width": size[0],
        "height": size[1]
      }} : null
    }});
  }}
  JSON.stringify({{
    "frontmost_app": {{
      "name": safe(() => app.name()),
      "pid": safe(() => app.unixId()),
      "bundle_id": safe(() => app.bundleIdentifier()),
      "role": safe(() => app.attributes.byName("AXRole").value())
    }},
    "window_count": count,
    "windows": kept
  }});
}}
"""
    try:
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", jxa],
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            check=False,
        )
    except FileNotFoundError:
        return None, "osascript not found"
    except subprocess.TimeoutExpired:
        return None, "osascript timed out"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return None, f"osascript rc={proc.returncode}: {err}"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"osascript returned invalid JSON: {exc}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="Accepted for MCP wrapper parity.")
    parser.add_argument("--no-windows", action="store_true", help="Skip System Events window read.")
    parser.add_argument("--max-windows", type=int, default=8)
    parser.add_argument("--jxa-timeout-secs", type=float, default=4.0)
    args = parser.parse_args(argv)

    started = time.time()
    max_windows = max(0, min(args.max_windows, 50))
    system = platform.system()
    errors: list[dict[str, Any]] = []
    ax_trusted, ax_error = _ax_is_trusted()
    if ax_error:
        errors.append({"stage": "ax_trust", "message": ax_error})

    frontmost: dict[str, Any] | None = None
    windows: list[dict[str, Any]] = []
    source_window_count: int | None = None
    truncated = False

    if system != "Darwin":
        status = "unsupported_platform"
    elif ax_trusted is False:
        status = "degraded"
    elif args.no_windows:
        status = "ready"
    else:
        jxa_payload, jxa_error = _frontmost_jxa(max_windows, args.jxa_timeout_secs)
        if jxa_error:
            errors.append({"stage": "system_events", "message": jxa_error})
            status = "degraded"
        else:
            frontmost = jxa_payload.get("frontmost_app") if jxa_payload else None
            windows = jxa_payload.get("windows", []) if jxa_payload else []
            source_window_count = jxa_payload.get("window_count") if jxa_payload else None
            truncated = bool(source_window_count is not None and len(windows) < source_window_count)
            status = "ready" if frontmost else "degraded"

    elapsed_ms = int((time.time() - started) * 1000)
    payload = {
        "schema": SCHEMA_VERSION,
        "captured_at": int(time.time()),
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "read_only": True,
        "status": status,
        "permission": {
            "ax_trusted": ax_trusted,
            "method": "AXIsProcessTrusted",
            "prompted": False,
        },
        "frontmost_app": frontmost,
        "windows": windows,
        "window_count": len(windows),
        "source_window_count": source_window_count,
        "limits": {
            "max_windows": max_windows,
            "truncated": truncated,
            "include_windows": not args.no_windows,
        },
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
