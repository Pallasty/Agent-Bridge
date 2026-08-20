#!/usr/bin/env python3
"""Reduce a native AX/CGWindow composite probe to content-free eligibility."""
from __future__ import annotations
import hashlib
import json
import sys
from typing import Any

SCHEMA = "agent_bridge.macos_ax_composite_identity_eligibility.v0"

def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def summarize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"schema": SCHEMA, "eligible_now": False, "reason": "probe_not_object"}
    scope = value.get("scope") if isinstance(value.get("scope"), dict) else {}
    candidates = value.get("candidates") if isinstance(value.get("candidates"), list) else []
    valid = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        window_id = item.get("cg_window_id")
        if (isinstance(window_id, int) and not isinstance(window_id, bool) and window_id > 0
                and item.get("unique_bijection_first") is True
                and item.get("unique_bijection_second") is True
                and item.get("stable_across_samples") is True
                and isinstance(item.get("focused_first"), bool)
                and isinstance(item.get("focused_second"), bool)):
            valid.append(item)
    eligible = bool(
        value.get("schema") == "agent_bridge.macos_ax_composite_identity_probe.v0"
        and value.get("status") == "eligible" and value.get("eligible_now") is True
        and value.get("read_only") is True and value.get("action_performed") is False
        and value.get("sample_count") == 2
        and isinstance(scope.get("bundle_id"), str) and scope["bundle_id"]
        and isinstance(scope.get("pid"), int) and not isinstance(scope.get("pid"), bool) and scope["pid"] > 0
        and isinstance(scope.get("process_launch_time_ms"), int)
        and len(valid) == len(candidates) and len(valid) >= 2
        and any(item["focused_first"] is False for item in valid)
    )
    identity_hashes = [
        _sha(f"{scope.get('bundle_id')}:{scope.get('pid')}:{scope.get('process_launch_time_ms')}:{item['cg_window_id']}")
        for item in valid
    ]
    return {
        "schema": SCHEMA, "eligible_now": eligible,
        "decision": "ELIGIBLE_COMPOSITE_IDENTITY_READONLY_ONLY" if eligible else "INELIGIBLE_COMPOSITE_IDENTITY",
        "reason": value.get("reason"), "sample_count": value.get("sample_count"),
        "sample_interval_ms": value.get("sample_interval_ms"), "candidate_count": len(valid),
        "unfocused_candidate_count": sum(item["focused_first"] is False for item in valid),
        "frontmost_process_sha256": _sha(f"{scope.get('bundle_id')}:{scope.get('pid')}:{scope.get('process_launch_time_ms')}") if scope else None,
        "composite_identity_sha256": identity_hashes,
        "all_bijections_unique": bool(valid) and len(valid) == len(candidates),
        "titles_retained": False, "bounds_retained": False, "raw_receipt_retained": False,
        "action_performed": False, "live_focus_authorized": False,
    }

def main() -> int:
    try: value = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError): value = None
    result = summarize(value)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["eligible_now"] else 2

if __name__ == "__main__": raise SystemExit(main())
