#!/usr/bin/env python3
"""macOS AX read-only feasibility probe.

This probe is intentionally narrow: it checks whether the current process is
trusted for Accessibility, then, only when already trusted, asks System Events
for frontmost-application/window metadata. It never clicks, types, focuses,
activates apps, changes permissions, or calls AXIsProcessTrustedWithOptions
with a prompt flag. Before invoking System Events, a no-ask Apple Events
permission preflight gates the subprocess. This is a best-effort prompt guard;
the effective sender identity and UI behavior still require validation on the
target Mac.
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

_APPLICATION_SERVICES = (
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)
_SYSTEM_EVENTS_BUNDLE_ID = b"com.apple.systemevents"
_TYPE_APPLICATION_BUNDLE_ID = 0x62756E64  # 'bund'
_TYPE_WILDCARD = 0x2A2A2A2A  # '****'


class _AEDesc(ctypes.Structure):
    _fields_ = [
        ("descriptor_type", ctypes.c_uint32),
        ("data_handle", ctypes.c_void_p),
    ]


_AUTOMATION_PERMISSION_ERRORS = {
    -1743: "not_permitted",
    -1744: "would_require_user_consent",
    -600: "target_not_running",
}


def _strict_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _frontmost_app_identity_valid(app: Any) -> bool:
    if not isinstance(app, dict):
        return False
    pid = app.get("pid")
    name = app.get("name")
    bundle_id = app.get("bundle_id")
    return bool(
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and (
            (isinstance(name, str) and bool(name.strip()))
            or (isinstance(bundle_id, str) and bool(bundle_id.strip()))
        )
    )


def _window_identity(window: dict[str, Any]) -> dict[str, Any]:
    """Describe whether a window identity can survive a later AX sample."""
    ax_identifier = window.get("ax_identifier")
    if isinstance(ax_identifier, str) and ax_identifier.strip():
        return {
            "kind": "ax_identifier",
            "value": ax_identifier.strip(),
            "stable_across_samples": True,
        }
    return {
        "kind": "sample_index",
        "value": str(window.get("index", "unknown")),
        "stable_across_samples": False,
    }


def _annotate_window_identities(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for window in windows:
        window["identity"] = _window_identity(window)
    return windows


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


def _system_events_automation_preflight() -> tuple[bool, str | None]:
    """Gate System Events JXA without asking macOS to show consent UI."""
    if platform.system() != "Darwin":
        return True, None

    try:
        app_services = ctypes.CDLL(_APPLICATION_SERVICES)
    except Exception as exc:  # noqa: BLE001 - fail closed before osascript
        return False, f"automation_preflight_framework_unavailable: {exc}"

    symbols = {}
    for name in (
        "AECreateDesc",
        "AEDeterminePermissionToAutomateTarget",
        "AEDisposeDesc",
    ):
        try:
            symbols[name] = getattr(app_services, name)
        except AttributeError:
            return False, f"automation_preflight_symbol_missing: {name}"

    create_desc = symbols["AECreateDesc"]
    create_desc.argtypes = [
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_long,
        ctypes.POINTER(_AEDesc),
    ]
    create_desc.restype = ctypes.c_int16

    determine_permission = symbols["AEDeterminePermissionToAutomateTarget"]
    determine_permission.argtypes = [
        ctypes.POINTER(_AEDesc),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_ubyte,
    ]
    determine_permission.restype = ctypes.c_int32

    dispose_desc = symbols["AEDisposeDesc"]
    dispose_desc.argtypes = [ctypes.POINTER(_AEDesc)]
    dispose_desc.restype = ctypes.c_int16

    target = _AEDesc()
    bundle_id = ctypes.create_string_buffer(_SYSTEM_EVENTS_BUNDLE_ID)
    try:
        create_status = int(
            create_desc(
                _TYPE_APPLICATION_BUNDLE_ID,
                ctypes.cast(bundle_id, ctypes.c_void_p),
                len(_SYSTEM_EVENTS_BUNDLE_ID),
                ctypes.byref(target),
            )
        )
    except Exception as exc:  # noqa: BLE001 - fail closed before osascript
        return False, f"automation_preflight_descriptor_create_error: {exc}"
    if create_status != 0:
        return (
            False,
            f"automation_preflight_descriptor_create_failed: status={create_status}",
        )

    permission_status: int | None = None
    permission_error: str | None = None
    dispose_status: int | None = None
    dispose_error: str | None = None
    try:
        permission_status = int(
            determine_permission(
                ctypes.byref(target),
                _TYPE_WILDCARD,
                _TYPE_WILDCARD,
                ctypes.c_ubyte(0),
            )
        )
    except Exception as exc:  # noqa: BLE001 - fail closed before osascript
        permission_error = f"automation_preflight_permission_check_error: {exc}"
    finally:
        try:
            dispose_status = int(dispose_desc(ctypes.byref(target)))
        except Exception as exc:  # noqa: BLE001 - fail closed before osascript
            dispose_error = f"automation_preflight_descriptor_dispose_error: {exc}"

    if dispose_error:
        return False, dispose_error
    if dispose_status != 0:
        return (
            False,
            f"automation_preflight_descriptor_dispose_failed: status={dispose_status}",
        )
    if permission_error:
        return False, permission_error
    if permission_status != 0:
        status_type = _AUTOMATION_PERMISSION_ERRORS.get(permission_status, "unknown")
        return (
            False,
            "automation_preflight_permission_denied: "
            f"type={status_type} status={permission_status}",
        )
    return True, None


def _frontmost_jxa(
    max_windows: int,
    timeout_secs: float,
) -> tuple[dict[str, Any] | None, str | None]:
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
  JSON.stringify({{frontmost_app: null, windows_read_ok: false, window_count: 0, windows: []}});
}} else {{
  const windowsResult = safe(() => app.windows());
  const windowsReadOk = windowsResult !== null;
  const wins = windowsResult || [];
  const countResult = safe(() => wins.length);
  const countReadOk = Number.isInteger(countResult) && countResult >= 0;
  const count = countReadOk ? countResult : 0;
  const kept = [];
  const limit = Math.min(count, {max_windows});
  for (let i = 0; i < limit; i++) {{
    const w = wins[i];
    const position = safe(() => w.position());
    const size = safe(() => w.size());
    kept.push({{
      "index": i,
      "ax_identifier": safe(() => w.attributes.byName("AXIdentifier").value()),
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
    "windows_read_ok": windowsReadOk && countReadOk,
    "window_count": count,
    "windows": kept
  }});
}}
"""
    automation_allowed, automation_error = _system_events_automation_preflight()
    if not automation_allowed:
        return None, automation_error or "automation_preflight_failed"
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
    parser.add_argument(
        "--no-windows",
        action="store_true",
        help="Skip System Events window read.",
    )
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
    windows_read_ok: bool | None = None
    truncated = False

    if system != "Darwin":
        status = "unsupported_platform"
    elif ax_trusted is not True:
        if ax_trusted is None and not ax_error:
            errors.append({"stage": "ax_trust", "message": "AX trust status unavailable"})
        status = "degraded"
    elif args.no_windows:
        status = "ready"
    else:
        jxa_payload, jxa_error = _frontmost_jxa(max_windows, args.jxa_timeout_secs)
        if jxa_error:
            errors.append({"stage": "system_events", "message": jxa_error})
            status = "degraded"
        elif not isinstance(jxa_payload, dict):
            errors.append({"stage": "system_events", "message": "invalid JXA payload"})
            status = "degraded"
        else:
            frontmost = jxa_payload.get("frontmost_app")
            raw_windows = jxa_payload.get("windows")
            source_window_count = jxa_payload.get("window_count")
            windows_read_ok = jxa_payload.get("windows_read_ok")
            if isinstance(raw_windows, list) and all(
                isinstance(window, dict) for window in raw_windows
            ):
                windows = _annotate_window_identities(raw_windows)
            else:
                errors.append(
                    {"stage": "system_events_windows", "message": "invalid windows payload"}
                )
            if windows_read_ok is not True:
                errors.append(
                    {"stage": "system_events_windows", "message": "window enumeration failed"}
                )
            if not _strict_nonnegative_int(source_window_count):
                errors.append(
                    {
                        "stage": "system_events_window_count",
                        "message": "invalid source window count",
                    }
                )
            elif source_window_count < len(windows):
                errors.append(
                    {
                        "stage": "system_events_window_count",
                        "message": "source window count is smaller than returned windows",
                    }
                )
            truncated = bool(
                _strict_nonnegative_int(source_window_count)
                and source_window_count > len(windows)
            )
            status = (
                "ready"
                if _frontmost_app_identity_valid(frontmost)
                and windows_read_ok is True
                and _strict_nonnegative_int(source_window_count)
                and source_window_count >= len(windows)
                and not errors
                else "degraded"
            )

    elapsed_ms = int((time.time() - started) * 1000)
    app_identity_valid = _frontmost_app_identity_valid(frontmost)
    counts_consistent = bool(
        _strict_nonnegative_int(source_window_count)
        and source_window_count == len(windows)
    )
    if args.no_windows:
        coverage_complete = status == "ready" and ax_trusted is True and not errors
        incomplete_reasons = [] if coverage_complete else ["ax_trust_incomplete"]
    else:
        incomplete_reasons = []
        if status != "ready":
            incomplete_reasons.append("probe_not_ready")
        if not app_identity_valid:
            incomplete_reasons.append("frontmost_app_identity_invalid")
        if windows_read_ok is not True:
            incomplete_reasons.append("window_enumeration_unconfirmed")
        if not counts_consistent:
            incomplete_reasons.append("window_counts_incomplete")
        if truncated:
            incomplete_reasons.append("window_enumeration_truncated")
        if errors:
            incomplete_reasons.append("probe_errors")
        incomplete_reasons = list(dict.fromkeys(incomplete_reasons))
        coverage_complete = not incomplete_reasons

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
        "windows_read_ok": windows_read_ok,
        "app_identity_valid": app_identity_valid,
        "counts_consistent": counts_consistent,
        "coverage_complete": coverage_complete,
        "incomplete_reasons": incomplete_reasons,
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
