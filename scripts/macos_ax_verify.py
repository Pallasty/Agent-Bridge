#!/usr/bin/env python3
"""macOS AX read-only verifier.

Re-observes the same bounded surface as macos_ax_probe.py and checks one
predicate. It never prompts, activates apps, focuses windows, clicks, types, or
mutates desktop state.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from typing import Any

from macos_ax_probe import _ax_is_trusted, _frontmost_jxa

SCHEMA_VERSION = "macos_ax_verify/v0"
EXPECTS = {
    "ax_trusted_is",
    "frontmost_app_is",
    "window_appeared",
    "window_gone",
    "window_focused",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains(haystack: Any, needle: str | None) -> bool:
    if needle is None or needle == "":
        return True
    return _norm(needle) in _norm(haystack)


def _bool_arg(value: str | None) -> bool | None:
    if value is None:
        return None
    lower = value.strip().lower()
    if lower in {"true", "1", "yes", "y"}:
        return True
    if lower in {"false", "0", "no", "n"}:
        return False
    return None


def _selector(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "app": args.app,
        "bundle_id": args.bundle_id,
        "pid": args.pid,
        "title": args.title,
        "role": args.role,
        "index": args.index,
        "state": args.state,
    }


def _probe(max_windows: int, jxa_timeout_secs: float) -> tuple[dict[str, Any], str | None]:
    started = time.time()
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
    else:
        jxa_payload, jxa_error = _frontmost_jxa(max_windows, jxa_timeout_secs)
        if jxa_error:
            errors.append({"stage": "system_events", "message": jxa_error})
            status = "degraded"
        else:
            frontmost = jxa_payload.get("frontmost_app") if jxa_payload else None
            windows = jxa_payload.get("windows", []) if jxa_payload else []
            source_window_count = jxa_payload.get("window_count") if jxa_payload else None
            truncated = bool(source_window_count is not None and len(windows) < source_window_count)
            status = "ready" if frontmost else "degraded"

    probe = {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
        },
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
            "include_windows": True,
        },
        "errors": errors,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
    if status == "unsupported_platform":
        return probe, "unsupported_platform"
    if status == "degraded":
        return probe, "probe_degraded"
    return probe, None


def _match_app(app: dict[str, Any] | None, args: argparse.Namespace) -> bool:
    if not app:
        return False
    if not _contains(app.get("name"), args.app):
        return False
    if not _contains(app.get("bundle_id"), args.bundle_id):
        return False
    if args.pid is not None and app.get("pid") != args.pid:
        return False
    return True


def _match_window(window: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.index is not None and window.get("index") != args.index:
        return False
    if not _contains(window.get("title"), args.title):
        return False
    if not _contains(window.get("role"), args.role):
        return False
    return True


def _evaluate(args: argparse.Namespace, probe: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], str | None]:
    expect = args.expect
    if expect == "ax_trusted_is":
        wanted = _bool_arg(args.state)
        if wanted is None:
            return False, [], "state must be true/false for ax_trusted_is"
        actual = probe.get("permission", {}).get("ax_trusted")
        return actual is wanted, [{"ax_trusted": actual}], None

    app = probe.get("frontmost_app")
    if expect == "frontmost_app_is":
        matched = _match_app(app, args)
        return matched, [app] if matched and app else [], None

    windows = probe.get("windows") or []
    candidates = [w for w in windows if _match_window(w, args)]
    if expect == "window_appeared":
        return bool(candidates), candidates, None
    if expect == "window_gone":
        return not candidates, candidates, None
    if expect == "window_focused":
        focused = [w for w in candidates if w.get("focused") is True]
        return bool(focused), focused, None
    return False, [], f"unsupported expect: {expect}"


def _recover(expect: str, verdict: str, probe_error: str | None) -> str:
    if verdict == "verified":
        return "proceed"
    if probe_error == "unsupported_platform":
        return "replan"
    if probe_error:
        return "escalate"
    if expect in {"window_appeared", "window_focused", "frontmost_app_is"}:
        return "retry"
    return "proceed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="Accepted for MCP wrapper parity.")
    parser.add_argument("--expect", choices=sorted(EXPECTS), required=True)
    parser.add_argument("--app", help="Frontmost app name substring.")
    parser.add_argument("--bundle-id", help="Frontmost app bundle id substring.")
    parser.add_argument("--pid", type=int, help="Frontmost app pid.")
    parser.add_argument("--title", help="Window title substring.")
    parser.add_argument("--role", help="Window AXRole substring.")
    parser.add_argument("--index", type=int, help="Window index from macos_ax_probe.")
    parser.add_argument("--state", help="Expected boolean state for ax_trusted_is.")
    parser.add_argument("--max-windows", type=int, default=8)
    parser.add_argument("--jxa-timeout-secs", type=float, default=4.0)
    parser.add_argument("--timeout", type=float, default=4.0, help="Poll timeout seconds.")
    parser.add_argument("--poll-interval", type=float, default=0.3)
    parser.add_argument("--settle", type=float, default=0.0)
    args = parser.parse_args(argv)

    started = time.time()
    if args.settle > 0:
        time.sleep(min(args.settle, 5.0))

    max_windows = max(0, min(args.max_windows, 50))
    timeout = max(0.0, min(args.timeout, 30.0))
    poll_interval = max(0.05, min(args.poll_interval, 5.0))
    deadline = time.time() + timeout
    polls = 0
    last_probe: dict[str, Any] = {}
    last_matches: list[dict[str, Any]] = []
    error: str | None = None
    verified = False

    while True:
        polls += 1
        probe, probe_error = _probe(max_windows, args.jxa_timeout_secs)
        last_probe = probe
        if probe_error and args.expect != "ax_trusted_is":
            matched, matches, eval_error = False, [], probe_error
        else:
            matched, matches, eval_error = _evaluate(args, probe)
        last_matches = matches
        error = eval_error or probe_error
        if eval_error:
            break
        if matched:
            verified = True
            break
        if time.time() >= deadline:
            break
        time.sleep(poll_interval)

    held_after_ms = int((time.time() - started) * 1000)
    verdict = "verified" if verified else ("error" if error else "unmet")
    payload = {
        "schema": SCHEMA_VERSION,
        "ts": int(time.time()),
        "expect": args.expect,
        "selector": _selector(args),
        "scope": {
            "source": "frontmost_app_windows",
            "platform": last_probe.get("platform", {}),
            "max_windows": max_windows,
        },
        "verdict": verdict,
        "recover": _recover(args.expect, verdict, error),
        "change": None,
        "held_after_ms": held_after_ms if verified else None,
        "polls": polls,
        "observed": {
            "probe_status": last_probe.get("status"),
            "permission": last_probe.get("permission"),
            "frontmost_app": last_probe.get("frontmost_app"),
            "count": len(last_matches),
            "matches": last_matches,
            "window_count": last_probe.get("window_count"),
            "source_window_count": last_probe.get("source_window_count"),
            "errors": last_probe.get("errors", []),
        },
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False))
    if verdict == "verified":
        return 0
    if verdict == "unmet":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
