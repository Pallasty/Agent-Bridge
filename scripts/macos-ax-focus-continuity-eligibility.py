#!/usr/bin/env python3
"""Reduce one macos_ax_probe receipt to a content-free focus eligibility fact."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from typing import Any


SCHEMA = "agent_bridge.macos_ax_focus_continuity_eligibility.v0"


def _digest(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def summarize(value: Any, *, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not isinstance(value, dict):
        return {"schema": SCHEMA, "status": "ineligible", "reason": "probe_not_object"}
    windows = value.get("windows") if isinstance(value.get("windows"), list) else []
    stable: list[dict[str, Any]] = []
    complete = True
    for window in windows:
        identity = window.get("identity") if isinstance(window, dict) else None
        valid = (
            isinstance(window, dict)
            and isinstance(identity, dict)
            and identity.get("kind") == "ax_identifier"
            and identity.get("stable_across_samples") is True
            and isinstance(window.get("ax_identifier"), str)
            and bool(window["ax_identifier"])
            and identity.get("value") == window["ax_identifier"]
            and isinstance(window.get("title"), str)
            and isinstance(window.get("role"), str)
            and bool(window["role"])
            and isinstance(window.get("focused"), bool)
        )
        complete = complete and valid
        if valid:
            stable.append(window)
    identities = [window["ax_identifier"] for window in stable]
    unfocused = [window for window in stable if window["focused"] is False]
    frontmost = value.get("frontmost_app") if isinstance(value.get("frontmost_app"), dict) else {}
    captured_at = value.get("captured_at")
    age_ms = None
    if isinstance(captured_at, int) and not isinstance(captured_at, bool):
        age_ms = max(0, int((now - captured_at) * 1000))
    permission = value.get("permission") if isinstance(value.get("permission"), dict) else {}
    limits = value.get("limits") if isinstance(value.get("limits"), dict) else {}
    errors = value.get("errors") if isinstance(value.get("errors"), list) else []
    incomplete_reasons = (
        value.get("incomplete_reasons")
        if isinstance(value.get("incomplete_reasons"), list)
        else []
    )
    eligible = all(
        (
            value.get("schema") == "macos_ax_probe/v0",
            value.get("status") == "ready",
            value.get("read_only") is True,
            isinstance(value.get("platform"), dict)
            and value["platform"].get("system") == "Darwin",
            permission.get("ax_trusted") is True,
            permission.get("prompted") is False,
            value.get("windows_read_ok") is True,
            value.get("coverage_complete") is True,
            value.get("counts_consistent") is True,
            limits.get("truncated") is False,
            value.get("errors") == [],
            value.get("incomplete_reasons") == [],
            value.get("app_identity_valid") is True,
            isinstance(frontmost.get("pid"), int)
            and not isinstance(frontmost.get("pid"), bool)
            and frontmost["pid"] > 0,
            value.get("window_count") == len(windows),
            value.get("source_window_count") == len(windows),
            complete,
            len(stable) >= 2,
            len(identities) == len(set(identities)),
            len(unfocused) >= 1,
            age_ms is not None and age_ms <= 5000,
        )
    )
    return {
        "schema": SCHEMA,
        "status": "eligible" if eligible else "ineligible",
        "eligible_now": eligible,
        "probe_schema": value.get("schema"),
        "probe_status": value.get("status"),
        "platform_system": value.get("platform", {}).get("system")
        if isinstance(value.get("platform"), dict)
        else None,
        "ax_trusted": permission.get("ax_trusted"),
        "permission_prompted": permission.get("prompted"),
        "coverage_complete": value.get("coverage_complete"),
        "counts_consistent": value.get("counts_consistent"),
        "truncated": limits.get("truncated"),
        "errors_empty": value.get("errors") == [],
        "incomplete_reasons_empty": value.get("incomplete_reasons") == [],
        "error_stages": sorted(
            {
                error.get("stage")
                for error in errors
                if isinstance(error, dict)
                and isinstance(error.get("stage"), str)
                and error["stage"]
            }
        ),
        "incomplete_reason_codes": sorted(
            reason for reason in incomplete_reasons if isinstance(reason, str)
        ),
        "frontmost_scope_sha256": _digest(
            f"{frontmost.get('bundle_id')}:{frontmost.get('pid')}"
        ),
        "returned_window_count": len(windows),
        "source_window_count": value.get("source_window_count"),
        "all_returned_selectors_complete": complete,
        "stable_window_count": len(stable),
        "stable_identities_unique": len(identities) == len(set(identities)),
        "unfocused_stable_window_count": len(unfocused),
        "stable_identity_sha256": [_digest(identity) for identity in identities],
        "probe_age_ms_at_summary": age_ms,
        "titles_retained": False,
        "raw_receipt_retained": False,
        "action_performed": False,
    }


def main() -> int:
    try:
        value = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = None
    result = summarize(value)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("eligible_now") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
